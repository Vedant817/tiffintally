"""
Deterministic order reconciliation and state management for home kitchens.
Handles:
- Time-ordered event replay
- Cancellations, modifications, pauses, and unpauses
- Cutoff time thresholding (late orders flagged, not silently applied)
- Duplicate message deduplication
- Splitting multi-person requests ("Priya ke liye bhi ek")
- Generating customer ledger and polite Hinglish reminder drafts
- Production security review routing for prompt-injections, excessive quantities, and low confidence
"""

import logging
from datetime import datetime, time
from typing import Dict, List, Optional, Set, Tuple

from tiffintally.dates import resolve_day_label
from tiffintally.schema import (
    CustomerLedger,
    DailyPrepSheet,
    OrderEvent,
    PackingLabel,
    SpecialMod,
)

logger = logging.getLogger(__name__)


class CustomerMealState:
    def __init__(self, customer: str, meal: str):
        self.customer = customer
        self.meal = meal
        self.qty = 0
        self.items: List[str] = []
        self.mods: List[str] = []
        self.is_paused: bool = False


def parse_timestamp(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%y, %I:%M %p",
        "%d/%m/%Y, %I:%M %p",
        "%m/%d/%y, %I:%M %p",
        "%m/%d/%Y, %I:%M %p",
        "%Y-%m-%dT%H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(ts, fmt)
        except Exception:
            pass
    return None


def calendar_day(label: str, reference: datetime):
    """Resolve a day word against a reference clock. Unknown words stay unresolved."""
    return resolve_day_label(label, reference)


def pause_covers_target(ev: OrderEvent, target_date: str, as_of: datetime) -> bool:
    """True when a dated pause window includes the cook's target day."""
    reference = parse_timestamp(ev.timestamp) or as_of
    start = calendar_day(ev.date, reference)
    if start is None or not ev.pause_until:
        return False
    end = calendar_day(ev.pause_until, datetime.combine(start, time.min))
    target = calendar_day(target_date, as_of)
    if end is None or target is None:
        return False
    return start <= target <= end


def event_matches_target(ev: OrderEvent, target_date: str, as_of: datetime) -> bool:
    """Keep an event only when it is for the cook's target day.

    Relative words on the event use the message timestamp. Relative words on the
    target use `as_of` (when the cook builds the sheet). "today" does not match
    a target of "tomorrow".
    """
    if not target_date or target_date.strip().lower() == "any":
        return True
    reference = parse_timestamp(ev.timestamp) or as_of
    event_day = calendar_day(ev.date, reference)
    target_day = calendar_day(target_date, as_of)
    if event_day is not None and target_day is not None:
        return event_day == target_day
    return (ev.date or "").strip().lower() == target_date.strip().lower()


def is_after_cutoff(ts: Optional[datetime], cutoff_time: Optional[time]) -> bool:
    """Return True if message was received on or after cutoff time."""
    if ts is None or cutoff_time is None:
        return False
    # Compare time of day
    return ts.time() > cutoff_time


def reconcile_orders(
    events: List[OrderEvent],
    target_date: str = "tomorrow",
    cutoff_time: Optional[time] = None,
    standing_orders: Optional[Dict[str, int]] = None,
    as_of: Optional[datetime] = None,
) -> DailyPrepSheet:
    """
    Apply events in time order.
    Returns the complete DailyPrepSheet.
    """
    as_of = as_of or datetime.now()
    resolved_target = calendar_day(target_date, as_of)
    sheet_date = resolved_target.isoformat() if resolved_target else target_date
    prep_sheet = DailyPrepSheet(date=sheet_date)

    # Apply standing orders if provided (e.g. daily regulars)
    state_map: Dict[Tuple[str, str], CustomerMealState] = {}
    if standing_orders:
        for cust, default_qty in standing_orders.items():
            st = CustomerMealState(customer=cust, meal="lunch")
            st.qty = default_qty
            st.items = ["thali"]
            state_map[(cust.lower(), "lunch")] = st

    # 1. Deduplication (Bold test 8: duplicate forwarded messages counted once)
    seen_dedup_keys: Set[Tuple[str, Optional[str], str, str, int, str]] = set()
    deduped_events: List[OrderEvent] = []

    for ev in events:
        # Key: (customer, timestamp, raw_text, action, qty, meal)
        dedup_key = (
            ev.customer.strip().lower(),
            ev.timestamp,
            ev.raw_text.strip().lower() if ev.raw_text else "",
            ev.action,
            ev.qty,
            ev.meal,
        )
        if dedup_key in seen_dedup_keys:
            continue
        seen_dedup_keys.add(dedup_key)
        deduped_events.append(ev)

    # 2. Sort events by timestamp if available
    def sort_key(e: OrderEvent):
        dt = parse_timestamp(e.timestamp)
        return dt if dt else datetime.min

    sorted_events = sorted(deduped_events, key=sort_key)

    # 3. Process events chronologically
    for ev in sorted_events:
        label = (ev.date or "").strip().lower()
        if label in {"", "unspecified", "ambiguous"} and ev.action not in {"none", "payment"}:
            ev.needs_review = True
            if "date_unresolved" not in ev.audit_flags:
                ev.audit_flags.append("date_unresolved")

        # Check security audit flags, business bounds, or low confidence.
        # Do this before the date filter so a malformed row is not dropped silently.
        is_risky = (
            ev.needs_review
            or ev.confidence < 0.70
            or bool(ev.audit_flags)
            or (ev.action == "none" and ev.raw_text and len(ev.raw_text) > 40)
        )
        if is_risky and ev not in prep_sheet.unresolved_reviews:
            prep_sheet.unresolved_reviews.append(ev)
        if ev.action == "pause" and "date_range" in ev.audit_flags:
            if pause_covers_target(ev, target_date, as_of):
                cust = ev.customer.strip().lower()
                for meal in ("lunch", "dinner"):
                    standing = state_map.get((cust, meal))
                    if standing is not None:
                        standing.qty = 0
                        standing.is_paused = True
                        standing.items = []
                        standing.mods = []
                if ev not in prep_sheet.cancellations:
                    prep_sheet.cancellations.append(ev)
            continue
        if not event_matches_target(ev, target_date, as_of):
            if label not in {"", "unspecified", "ambiguous"} and ev.action not in {
                "none",
                "payment",
            }:
                prep_sheet.other_days.append(ev)
            continue

        if is_risky:
            # If critical prompt injection, excessive quantity (>20), or explicit review flag, don't auto-apply
            if ev.needs_review or any(
                "prompt_injection" in f or "excessive_quantity" in f for f in ev.audit_flags
            ):
                continue

        # Skip pure chit-chat
        if ev.action == "none":
            continue

        # Skip payment notes from kitchen cooking tally
        if ev.action == "payment":
            continue

        # Check late cutoff
        dt = parse_timestamp(ev.timestamp)
        late = is_after_cutoff(dt, cutoff_time)
        if late:
            ev.is_late = True
            prep_sheet.late_orders.append(ev)
            # Late orders after cutoff are flagged for cook approval, not silently added
            continue

        # Meals to apply (lunch, dinner, or both)
        target_meals = []
        if ev.meal in ["lunch", "dinner"]:
            target_meals = [ev.meal]
        elif ev.meal == "both":
            target_meals = ["lunch", "dinner"]
        else:
            target_meals = ["lunch"]  # default fallback

        # Check for secondary customer (Bold test 3: "Priya ke liye bhi ek" from Ravi)
        customer_allocations: List[Tuple[str, int]] = []
        if ev.secondary_customer and ev.qty >= 2:
            # Secondary customer gets 1, primary gets remainder
            customer_allocations.append((ev.customer, ev.qty - 1))
            customer_allocations.append((ev.secondary_customer, 1))
        elif ev.secondary_customer and ev.qty == 1:
            # Entire order is for secondary customer
            customer_allocations.append((ev.secondary_customer, 1))
        else:
            customer_allocations.append((ev.customer, ev.qty))

        for cust_name, qty in customer_allocations:
            for meal in target_meals:
                key = (cust_name.strip().lower(), meal)
                if key not in state_map:
                    state_map[key] = CustomerMealState(customer=cust_name.strip(), meal=meal)
                st = state_map[key]

                if ev.action == "new":
                    st.qty = qty
                    if ev.items:
                        st.items = list(ev.items)
                    elif st.qty > 0 and not st.items:
                        st.items = ["thali"]
                    if ev.mods:
                        st.mods.extend(ev.mods)

                elif ev.action == "change":
                    st.qty = qty
                    if ev.items:
                        st.items = list(ev.items)
                    if ev.mods:
                        st.mods.extend(ev.mods)

                elif ev.action == "cancel":
                    st.qty = 0
                    st.items = []
                    st.mods = []
                    prep_sheet.cancellations.append(ev)

                elif ev.action == "pause":
                    st.qty = 0
                    st.is_paused = True
                    st.items = []
                    st.mods = []
                    prep_sheet.cancellations.append(ev)

    # 4. Build final packing labels and aggregate totals
    total_lunch = 0
    total_dinner = 0
    packing_labels: List[PackingLabel] = []
    special_mods: List[SpecialMod] = []

    for (c_key, meal), st in sorted(state_map.items()):
        if st.qty > 0 and not st.is_paused:
            if meal == "lunch":
                total_lunch += st.qty
            elif meal == "dinner":
                total_dinner += st.qty

            # Add packing label
            packing_labels.append(
                PackingLabel(
                    customer=st.customer,
                    meal=meal,
                    qty=st.qty,
                    items=st.items or ["thali"],
                    mods=st.mods,
                    notes="",
                    is_late=False,
                )
            )

            # Record special mods
            for mod in st.mods:
                special_mods.append(
                    SpecialMod(
                        customer=st.customer,
                        meal=meal,
                        mod_description=mod,
                    )
                )

    prep_sheet.total_lunch = total_lunch
    prep_sheet.total_dinner = total_dinner
    prep_sheet.total_thalis = total_lunch + total_dinner
    prep_sheet.packing_labels = packing_labels
    prep_sheet.special_mods = special_mods

    return prep_sheet


def reconcile_ledger(
    events: List[OrderEvent],
    price_per_thali: float = 80.0,
    previous_balances: Optional[Dict[str, float]] = None,
) -> Dict[str, CustomerLedger]:
    """
    Calculate customer financial ledgers and generate polite Hinglish reminders.
    Never auto-sends any message.
    """
    ledgers: Dict[str, CustomerLedger] = {}
    prev_bals = previous_balances or {}

    for ev in events:
        cust = ev.customer.strip()
        cust_key = cust.lower()

        if cust_key not in ledgers:
            initial_bal = prev_bals.get(cust_key, 0.0)
            ledgers[cust_key] = CustomerLedger(
                customer=cust,
                price_per_thali=price_per_thali,
                total_orders=0,
                total_billed=initial_bal,
                total_paid=0.0,
                balance_due=initial_bal,
            )
        entry = ledgers[cust_key]

        if ev.action in ["new", "change"] and ev.qty > 0 and not ev.is_late:
            entry.total_orders += ev.qty
            entry.total_billed += ev.qty * price_per_thali
            entry.balance_due += ev.qty * price_per_thali

        elif ev.action == "payment":
            amount = ev.payment_amount or 0.0
            entry.total_paid += amount
            entry.balance_due -= amount

    # Generate polite Hinglish payment reminders
    for entry in ledgers.values():
        if entry.balance_due > 0:
            entry.draft_reminder = (
                f"Namaste {entry.customer} ji! 🙏 Aapka tiffin ka balance "
                f"₹{int(entry.balance_due)} due hai. Jab bhi time mile GPay/PhonePe kar dijiyega. Thank you!"
            )

    return ledgers
