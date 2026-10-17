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

import hashlib
import json
import logging
from datetime import datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional, Set, Tuple

from tiffintally.clock import now as kitchen_now
from tiffintally.dates import resolve_day_label
from tiffintally.schema import (
    CustomerLedger,
    DailyPrepSheet,
    OrderEvent,
    PackingLabel,
    SpecialMod,
)
from tiffintally.security import InputGuardrail

logger = logging.getLogger(__name__)


def payment_id(event: OrderEvent) -> str:
    """Stable identity of one source payment; confirmations live only in a session."""
    identity = {
        key: getattr(event, key)
        for key in (
            "customer",
            "timestamp",
            "line_index",
            "raw_text",
            "payment_amount",
            "payment_note",
        )
    }
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


def payment_is_safe(event: OrderEvent) -> bool:
    return (
        event.action == "payment"
        and not event.needs_review
        and not event.audit_flags
        and event.confidence >= 0.7
        and event.payment_amount is not None
        and event.payment_amount > 0
        and not InputGuardrail().sanitize(event.raw_text).flags
    )


class CustomerMealState:
    def __init__(self, customer: str, meal: str):
        self.customer = customer
        self.meal = meal
        self.qty = 0
        self.items: List[str] = []
        self.mods: List[str] = []
        self.notes: str = ""
        self.is_paused: bool = False


# A message stamped between midnight and this hour belongs to the previous
# evening. Someone who types "kal lunch 2" at 00:30 means the coming day, not
# the one they are still awake in.
AFTER_MIDNIGHT_HOUR = 4

# Actions that add to an existing order rather than replacing it.
DELTA_ACTIONS = {"add"}


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

    Relative words on the event use the message timestamp, resolved against the
    evening it was written in: at 00:30 "kal" means the coming day, so it is not
    shifted a second time. Relative words on the target use `as_of` (when the
    cook builds the sheet). "today" does not match a target of "tomorrow".
    """
    if not target_date or target_date.strip().lower() == "any":
        return True
    reference = evening_reference(parse_timestamp(ev.timestamp), as_of)
    event_day = calendar_day(ev.date, reference)
    target_day = calendar_day(target_date, as_of)
    if event_day is not None and target_day is not None:
        return event_day == target_day
    return (ev.date or "").strip().lower() == target_date.strip().lower()


_RELATIVE_DATE_LABELS = {"today", "tomorrow", "aaj", "kal", "tonight"}


def is_after_midnight(ts: Optional[datetime]) -> bool:
    """True for a message stamped in the small hours."""
    return ts is not None and ts.hour < AFTER_MIDNIGHT_HOUR


def is_after_cutoff(ts: Optional[datetime], cutoff_time: Optional[time]) -> bool:
    """True when the message arrived too late to change tomorrow's plan.

    A message between midnight and AFTER_MIDNIGHT_HOUR is read as belonging to
    the previous evening, so 00:30 counts as late rather than as an early
    morning order that dodged the cutoff entirely.
    """
    if ts is None or cutoff_time is None:
        return False
    if ts.hour < AFTER_MIDNIGHT_HOUR:
        return True
    return ts.time() > cutoff_time


def evening_reference(ts: Optional[datetime], as_of: datetime) -> datetime:
    """Clock used to resolve relative words in a message.

    00:30 on the 16th is, for ordering purposes, the evening of the 15th.
    """
    if ts is not None and ts.hour < AFTER_MIDNIGHT_HOUR:
        return ts - timedelta(hours=AFTER_MIDNIGHT_HOUR)
    return ts or as_of


def sheet_state_qty(state_map: Dict[Tuple[str, str], CustomerMealState], ev: OrderEvent) -> int:
    """Plates this customer currently has for the meal a cancel refers to."""
    meals = ["lunch", "dinner"] if ev.meal == "both" else [ev.meal] if ev.meal else ["lunch"]
    return sum(
        state_map.get((ev.customer.strip().lower(), meal)).qty
        for meal in meals
        if state_map.get((ev.customer.strip().lower(), meal)) is not None
    )


def _cook_names(cook_names: Optional[List[str]]) -> set[str]:
    return {name.strip().lower() for name in (cook_names or []) if name.strip()}


def _conflicting_quantities(events: List[OrderEvent]) -> Set[Tuple[str, str]]:
    """(customer, meal) pairs whose orders contradict each other *within a minute*.

    Only same-minute pairs are a conflict. Android exports carry minute precision,
    so two different counts sharing a stamp genuinely cannot be ordered, and the
    cook has to decide.

    This used to also treat any two different counts for one customer on one day
    as a conflict, on the theory that it meant two people saved under one display
    name. That reading also matches an ordinary re-statement, and customers
    re-state constantly: "kal lunch 2" then "kal lunch 3 kar do" ten minutes
    later matched, so both rows were withheld and the sheet came up empty for
    that customer. Re-statements are handled by `_flag_restatements` instead,
    which applies the later message and surfaces the change.

    A `change` is a correction and an `add` is a delta, so neither is a conflict.
    """
    by_minute: Dict[Tuple[str, str, str], Set[int]] = {}
    for ev in events:
        if ev.action not in {"new", "change"} or ev.qty <= 0 or not ev.timestamp:
            continue
        key = (ev.customer.strip().lower(), ev.meal, ev.timestamp[:16])
        by_minute.setdefault(key, set()).add(ev.qty)

    return {(cust, meal) for (cust, meal, _minute), qtys in by_minute.items() if len(qtys) > 1}


def _flag_restatements(events: List[OrderEvent]) -> None:
    """Mark in place any order that a later message re-stated.

    Two different counts from one name for one meal on one day is ambiguous, and
    the text cannot tell the two readings apart. It is either a customer
    correcting herself, or two different people saved under one display name.

    Both readings matter before packing, so both are surfaced. The later message
    is applied, because it is the most recent thing that customer said, and the
    row is flagged `restated` so it lands in unresolved_reviews instead of
    silently changing the count. Withholding both rows, as the conflict check
    used to, is what printed an empty sheet for a customer who simply corrected
    herself.

    A `change` is a correction and an `add` is a delta, so neither restates.

    `needs_review` is deliberately left alone. That flag means "withhold this
    row", and withholding a restatement is the bug this replaced.
    """
    seen: Dict[Tuple[str, str, str], int] = {}
    for ev in events:
        if ev.action != "new" or ev.qty <= 0:
            continue
        day = (ev.date or "").strip().lower() or (ev.timestamp or "")[:10]
        key = (ev.customer.strip().lower(), ev.meal, day)
        previous = seen.get(key)
        if previous is not None and previous != ev.qty and "restated" not in ev.audit_flags:
            ev.audit_flags.append("restated")
        seen[key] = ev.qty


def _sort_key(ev: OrderEvent):
    """Time order with a stable tiebreak.

    WhatsApp exports carry minute precision, so two messages can share a stamp.
    `line_index` is the position in the export, which makes the result depend on
    the file rather than on dict ordering. `list.index` is not usable here: two
    distinct events compare equal under pydantic's field equality.
    """
    return (parse_timestamp(ev.timestamp) or datetime.min, ev.line_index)


def _final_states(
    events: List[OrderEvent],
    target_date: str,
    as_of: datetime,
    cutoff_time: Optional[time] = None,
    cook_names: Optional[List[str]] = None,
    accept_late_cancels: bool = False,
) -> Dict[Tuple[str, str, str], CustomerMealState]:
    """Replay events into the last known plate count per (customer, day, meal).

    Keyed by day as well as customer: a pause for Thursday must not erase the
    customer's plate for Friday, and a ledger line has to add up across days.

    This is the single source of truth for the prep sheet and for the bill.
    Billing used to sum every `new` and `change`, so "lunch 2" followed by
    "change to 3" billed five thalis.
    """
    state_map: Dict[Tuple[str, str, str], CustomerMealState] = {}

    days = {
        calendar_day(ev.date, evening_reference(parse_timestamp(ev.timestamp), as_of))
        for ev in events
        if ev.action not in {"none", "payment"}
    }
    target = calendar_day(target_date, as_of)
    if target_date != "any":
        days = {target} if target else set()
    for day in sorted(day for day in days if day is not None):
        _, day_map = _replay_day(
            events,
            day.isoformat(),
            cutoff_time=cutoff_time,
            as_of=as_of,
            cook_names=cook_names,
            accept_late_cancels=accept_late_cancels,
        )
        for (cust, meal), state in day_map.items():
            state_map[(cust, day.isoformat(), meal)] = state

    return state_map


def _replay_day(
    events: List[OrderEvent],
    target_date: str = "tomorrow",
    cutoff_time: Optional[time] = None,
    standing_orders: Optional[Dict[str, int]] = None,
    as_of: Optional[datetime] = None,
    cook_names: Optional[List[str]] = None,
    accept_late_cancels: bool = False,
) -> tuple[DailyPrepSheet, Dict[Tuple[str, str], CustomerMealState]]:
    """
    Apply events in time order.
    Returns the complete DailyPrepSheet.

    `cook_names` are display names of the cook herself. In a group her own
    "ok kal lunch 2 done" must not be counted as a customer's order.

    `accept_late_cancels` applies cancels that arrived after the cutoff. By
    default they are shown as a pending reduction instead: a late cancel saves
    food, but only the cook knows whether she has already packed it.
    """
    as_of = parse_timestamp(as_of) if isinstance(as_of, str) else as_of
    as_of = as_of or kitchen_now()
    events = [ev.model_copy(deep=True) for ev in events]
    for event in events:
        audit = InputGuardrail().sanitize(event.raw_text)
        if not audit.is_safe or event.qty > 20:
            event.needs_review = True
            event.audit_flags.extend(flag for flag in audit.flags if flag not in event.audit_flags)
            if event.qty > 20:
                event.audit_flags.append("excessive_quantity_at_replay")
    resolved_target = calendar_day(target_date, as_of)
    sheet_date = resolved_target.isoformat() if resolved_target else target_date
    prep_sheet = DailyPrepSheet(date=sheet_date)

    state_map: Dict[Tuple[str, str], CustomerMealState] = {}
    if standing_orders:
        for cust, default_qty in standing_orders.items():
            st = CustomerMealState(customer=cust, meal="lunch")
            st.qty = default_qty
            st.items = ["thali"]
            state_map[(cust.lower(), "lunch")] = st

    cooks = _cook_names(cook_names)
    conflicting = _conflicting_quantities(
        [ev for ev in events if event_matches_target(ev, target_date, as_of)]
    )
    cook_message_count = 0

    # 1. Deduplication. A forwarded message repeated twice is one order.
    seen_dedup_keys: Set[Tuple[str, Optional[str], str, str, int, str]] = set()
    deduped_events: List[OrderEvent] = []

    for ev in events:
        if cooks and ev.customer.strip().lower() in cooks:
            # The cook's own line. Counted so the sheet can say how many were
            # skipped, but never a plate and never a review row: she wrote it.
            cook_message_count += 1
            continue
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

    # 2. Stable order: minute-precision stamps tie-break on position in the
    #    export, so the sheet depends on the file and not on dict ordering.
    sorted_events = sorted(deduped_events, key=_sort_key)

    # Flag re-statements before anything is applied, so the change is visible on
    # the sheet even though the later count is the one that gets used.
    _flag_restatements([ev for ev in sorted_events if event_matches_target(ev, target_date, as_of)])

    # 3. Process events chronologically.
    for ev in sorted_events:
        label = (ev.date or "").strip().lower()
        if label in {"", "unspecified", "ambiguous"} and ev.action not in {"none", "payment"}:
            ev.needs_review = True
            if "date_unresolved" not in ev.audit_flags:
                ev.audit_flags.append("date_unresolved")

        is_conflicting = (
            ev.customer.strip().lower(),
            ev.meal,
        ) in conflicting and ev.action in {"new", "change", "add"}

        # "kal" written at 00:30 is genuinely ambiguous: tonight or the coming
        # morning. The evening reading is applied, and the row is surfaced so the
        # cook can confirm rather than cook the wrong day.
        after_midnight = is_after_midnight(parse_timestamp(ev.timestamp)) and (
            label in _RELATIVE_DATE_LABELS
        )
        if after_midnight and "after_midnight" not in ev.audit_flags:
            ev.audit_flags.append("after_midnight")

        is_risky = (
            ev.needs_review
            or ev.confidence < 0.70
            or bool(ev.audit_flags)
            or is_conflicting
            or after_midnight
            or (ev.action == "none" and ev.raw_text and len(ev.raw_text) > 40)
        )
        if is_risky and ev not in prep_sheet.unresolved_reviews:
            prep_sheet.unresolved_reviews.append(ev)
        if is_conflicting and "same_minute_conflict" not in ev.audit_flags:
            ev.audit_flags.append("same_minute_conflict")

        # A dated pause window only removes the days it covers.
        if ev.action == "pause" and "date_range" in ev.audit_flags:
            if pause_covers_target(ev, target_date, as_of):
                cust = ev.customer.strip().lower()
                for meal in ("lunch", "dinner"):
                    st = state_map.get((cust, meal))
                    if st is not None:
                        st.qty = 0
                        st.is_paused = True
                        st.items = []
                        st.mods = []
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

        # A row the cook has to judge is not applied to the sheet.
        # An order whose only flag is an unrecognised request still packs,
        # with the customer's words on the label, and stays in the review list.
        request_only = set(ev.audit_flags) <= {"unrecognised_request"} and bool(ev.note)
        if not request_only and (
            ev.needs_review
            or ev.confidence < 0.70
            or any(f.startswith(("prompt_injection", "excessive_quantity")) for f in ev.audit_flags)
        ):
            continue

        if ev.action in {"none", "payment"}:
            continue

        # Late messages. A late cancel saves food, so offer it. A late extra
        # plate needs the cook's yes.
        dt = parse_timestamp(ev.timestamp)
        if is_after_cutoff(dt, cutoff_time):
            ev.is_late = True
            if ev.action in {"cancel", "pause"}:
                if accept_late_cancels:
                    _apply_event(ev, state_map)
                else:
                    prep_sheet.late_cancellations.append(ev)
            else:
                prep_sheet.late_orders.append(ev)
            continue

        if is_conflicting:
            continue

        if ev.action in {"cancel", "pause"}:
            prep_sheet.cancellations.append(ev)

        _apply_event(ev, state_map)

    # 4. Build packing labels and totals.
    total_lunch = 0
    total_dinner = 0
    packing_labels: List[PackingLabel] = []
    special_mods: List[SpecialMod] = []

    for (_c_key, meal), st in sorted(state_map.items()):
        if st.qty > 0 and not st.is_paused:
            if meal == "lunch":
                total_lunch += st.qty
            elif meal == "dinner":
                total_dinner += st.qty

            packing_labels.append(
                PackingLabel(
                    customer=st.customer,
                    meal=meal,
                    qty=st.qty,
                    items=st.items or ["thali"],
                    mods=st.mods,
                    notes=st.notes,
                    is_late=False,
                )
            )

            for mod in st.mods:
                special_mods.append(
                    SpecialMod(customer=st.customer, meal=meal, mod_description=mod)
                )

    prep_sheet.total_lunch = total_lunch
    prep_sheet.total_dinner = total_dinner
    prep_sheet.total_thalis = total_lunch + total_dinner
    prep_sheet.packing_labels = packing_labels
    prep_sheet.special_mods = special_mods
    prep_sheet.cook_names = sorted(cook_names or [])
    prep_sheet.cook_message_count = cook_message_count

    # Plates the pending late cancels would remove, summed from the current state.
    #
    # This used to start at the *number* of late cancels and then add each one's
    # plate count on top, so a 2-plate late cancel printed "3 plate(s) you no
    # longer need", and two customers' cancels still printed 3.
    prep_sheet.late_cancellation_total = sum(
        sheet_state_qty(state_map, ev) for ev in prep_sheet.late_cancellations
    )

    return prep_sheet, state_map


def reconcile_orders(
    events: List[OrderEvent],
    target_date: str = "tomorrow",
    cutoff_time: Optional[time] = None,
    standing_orders: Optional[Dict[str, int]] = None,
    as_of: Optional[datetime] = None,
    cook_names: Optional[List[str]] = None,
    accept_late_cancels: bool = False,
) -> DailyPrepSheet:
    """Pure projection of the shared daily replay used by the ledger."""
    return _replay_day(
        events, target_date, cutoff_time, standing_orders, as_of, cook_names, accept_late_cancels
    )[0]


def plates_by_day(
    events: List[OrderEvent],
    *,
    target_date: str = "any",
    as_of: Optional[datetime] = None,
    cutoff_time: Optional[time] = None,
    cook_names: Optional[List[str]] = None,
    accept_late_cancels: bool = False,
):
    states = _final_states(
        events, target_date, as_of or kitchen_now(), cutoff_time, cook_names, accept_late_cancels
    )
    return {key: state.qty for key, state in states.items()}


def _apply_event(ev: OrderEvent, state_map: Dict[Tuple[str, str], CustomerMealState]) -> None:
    """Fold one event into the plate-count state."""
    meals = (
        ["lunch", "dinner"]
        if ev.meal == "both"
        else [ev.meal]
        if ev.meal in ("lunch", "dinner")
        else ["lunch"]
    )

    # A cancel or pause carries qty 0 by definition, so it must not be filtered
    # out by a quantity guard. That guard is how "kal lunch cancel" left two
    # plates on the sheet and two plates on the bill.
    if ev.action in {"cancel", "pause"}:
        for meal in meals:
            recipient = ev.secondary_customer or ev.customer
            key = (recipient.strip().lower(), meal)
            st = state_map.setdefault(key, CustomerMealState(customer=recipient.strip(), meal=meal))
            st.qty = 0
            st.items = []
            st.mods = []
            st.is_paused = ev.action == "pause"
        # A cancel or pause removes plates. The brief's "already in the total"
        # sentence is only for rows that contributed plates, so this row stays unmarked.
        return

    if ev.action not in {"new", "change", "add"}:
        return

    # "roommate Priya ke liye bhi ek" is a second plate, not a replacement.
    allocations: List[Tuple[str, int]] = []
    if ev.secondary_customer and ev.qty >= ev.secondary_qty:
        allocations.append((ev.customer, ev.qty - ev.secondary_qty))
        allocations.append((ev.secondary_customer, ev.secondary_qty))
    elif ev.secondary_customer:
        return  # Impossible allocation, never invent plates.
    else:
        allocations.append((ev.customer, ev.qty))

    applied = False
    for cust_name, qty in allocations:
        if qty <= 0:
            continue
        for meal in meals:
            key = (cust_name.strip().lower(), meal)
            st = state_map.setdefault(key, CustomerMealState(customer=cust_name.strip(), meal=meal))

            if ev.action in DELTA_ACTIONS:
                st.qty += qty
                st.items = st.items or ["thali"]
            else:
                st.qty = qty
                st.items = list(ev.items) if ev.items else (st.items or ["thali"])
            st.is_paused = False
            if ev.mods:
                st.mods.extend(m for m in ev.mods if m not in st.mods)
            if ev.note:
                # A later message must not drop an earlier allergy or request.
                prior = [part for part in st.notes.split("; ") if part]
                if ev.note not in prior:
                    prior.append(ev.note)
                st.notes = "; ".join(prior)
            applied = True
    if applied:
        ev.applied_to_plate_count = True


def reconcile_ledger(
    events: List[OrderEvent],
    price_per_thali: float = 80.0,
    previous_balances: Optional[Dict[str, float]] = None,
    target_date: str = "any",
    as_of: Optional[datetime] = None,
    confirmed_payments: Optional[Set[str]] = None,
    cutoff_time: Optional[time] = None,
    cook_names: Optional[List[str]] = None,
    accept_late_cancels: bool = False,
) -> Dict[str, CustomerLedger]:
    """
    Calculate customer financial ledgers and generate polite Hinglish reminders.
    Never auto-sends any message.

    The bill comes from the reconciled plate count per (customer, day, meal),
    not from a sum of events, so a change is not billed twice and a cancelled
    meal is not billed at all.
    """
    as_of = as_of or kitchen_now()
    raw_prev = previous_balances or {}

    price_per_thali = money(price_per_thali)
    prev_bals: Dict[str, Decimal] = {}
    # The lookup key is lowercase. The label keeps the spelling from the CSV,
    # so an imported "Priya Sharma" is not shown as "priya sharma".
    display_names: Dict[str, str] = {}
    for key, value in raw_prev.items():
        norm = key.strip().lower()
        if norm not in display_names:
            display_names[norm] = key.strip()
        prev_bals[norm] = money(value)
    states = _final_states(events, target_date, as_of, cutoff_time, cook_names, accept_late_cancels)

    ledgers: Dict[str, CustomerLedger] = {
        name: CustomerLedger(
            customer=display_names[name],
            price_per_thali=price_per_thali,
            total_billed=amount,
            balance_due=amount,
        )
        for name, amount in prev_bals.items()
    }
    for (cust_key, _day, _meal), st in sorted(states.items()):
        if cust_key not in ledgers:
            opening = prev_bals.get(cust_key, 0.0)
            ledgers[cust_key] = CustomerLedger(
                customer=st.customer,
                price_per_thali=price_per_thali,
                total_orders=0,
                total_billed=opening,
                total_paid=0.0,
                balance_due=opening,
            )
        entry = ledgers[cust_key]
        entry.customer = st.customer
        entry.total_orders += st.qty
        entry.total_billed += st.qty * price_per_thali
        entry.balance_due += st.qty * price_per_thali

    # Payments and refunds credit the balance.
    seen_payments: Set[str] = set()
    for ev in events:
        cust_key = ev.customer.strip().lower()
        if ev.action != "payment":
            continue
        if not payment_is_safe(ev):
            continue
        identity = payment_id(ev)
        if identity in seen_payments:
            continue
        seen_payments.add(identity)
        if cust_key not in ledgers:
            opening = prev_bals.get(cust_key, 0.0)
            ledgers[cust_key] = CustomerLedger(
                customer=ev.customer.strip(),
                price_per_thali=price_per_thali,
                total_billed=opening,
                balance_due=opening,
            )
        entry = ledgers[cust_key]
        amount = money(ev.payment_amount or 0)
        if identity not in (confirmed_payments or set()):
            entry.total_claimed += amount
            continue
        is_refund = bool(ev.payment_note and "refund" in ev.payment_note.lower())
        if is_refund:
            entry.balance_due += amount
            entry.total_refunded += amount
        else:
            entry.total_paid += amount
            entry.balance_due -= amount

    for entry in ledgers.values():
        if entry.balance_due > 0:
            entry.draft_reminder = (
                f"Namaste {entry.customer} ji! 🙏 Aapka tiffin ka balance "
                f"₹{entry.balance_due:.2f} due hai. Jab bhi time mile GPay/PhonePe kar dijiyega. Thank you!"
            )

    return ledgers


def money(value) -> Decimal:
    amount = Decimal(str(value))
    if not amount.is_finite():
        raise ValueError("Money must be finite")
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
