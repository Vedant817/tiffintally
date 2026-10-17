"""Pydantic schemas and data models for TiffinTally."""

from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

MealType = Literal["lunch", "dinner", "both", "unspecified"]
# "add" is a delta: "ek aur" / "+1" adds a plate instead of replacing the count.
OrderAction = Literal["new", "change", "add", "cancel", "pause", "payment", "none"]


class OrderEvent(BaseModel):
    """Normalized structured event extracted from a customer message."""

    customer: str = Field(description="Name or pseudonymized ID of customer")
    date: str = Field(description="Target delivery date (YYYY-MM-DD) or relative indicator")
    meal: MealType = Field(
        default="lunch", description="Meal session (lunch/dinner/both/unspecified)"
    )
    qty: int = Field(default=1, ge=0, description="Number of thalis or meal packs")
    items: List[str] = Field(
        default_factory=list, description="Specific dish items (e.g. ['thali', 'extra roti'])"
    )
    mods: List[str] = Field(
        default_factory=list,
        description="Dietary customizations (e.g. ['no onion', 'roti nahi rice'])",
    )
    action: OrderAction = Field(
        default="new", description="Action type: new, change, add, cancel, pause, payment, none"
    )
    line_index: int = Field(
        default=0,
        description="Position of the source line in the export. Breaks ties between "
        "messages that share a minute-precision timestamp.",
    )
    payment_note: Optional[str] = Field(
        default=None, description="Payment note text if payment mentioned"
    )
    payment_amount: Optional[float] = Field(
        default=None, description="Extracted payment amount in INR"
    )
    pause_until: Optional[str] = Field(default=None, description="End date for pause if specified")
    secondary_customer: Optional[str] = Field(
        default=None, description="Referenced third-party customer (e.g. 'Priya ke liye')"
    )
    secondary_qty: int = Field(default=1, ge=0, description="Secondary share of total qty")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Extraction confidence score (0.0 to 1.0)"
    )
    raw_text: str = Field(default="", description="Original raw message text")
    note: Optional[str] = Field(
        default=None,
        description="Original wording the rules could not turn into a canonical mod. Shown to the cook.",
    )
    timestamp: Optional[str] = Field(default=None, description="ISO timestamp message was received")
    is_late: bool = Field(
        default=False, description="Flag indicating whether message was received after cutoff"
    )
    audit_flags: List[str] = Field(
        default_factory=list, description="Security and guardrail audit flags"
    )
    needs_review: bool = Field(default=False, description="Flag indicating manual review required")
    applied_to_plate_count: bool = Field(
        default=False,
        description="Set when reconcile folds this event's plates into the count. "
        "Cancels and pauses stay unmarked: they remove plates. "
        "The morning brief reads this mark instead of guessing from audit flags.",
    )


class ParsedMessage(BaseModel):
    """Raw parsed message line from WhatsApp export."""

    timestamp: datetime
    sender: str
    text: str
    is_media: bool = False
    is_system: bool = False
    raw_line: str = ""
    timestamp_unparsed: bool = False


class PackingLabel(BaseModel):
    """Kitchen packing label for a single customer delivery."""

    customer: str
    meal: str
    qty: int
    items: List[str] = Field(default_factory=list)
    mods: List[str] = Field(default_factory=list)
    notes: str = ""
    is_late: bool = False


class SpecialMod(BaseModel):
    """Highlighted dietary modification for the cook's station."""

    customer: str
    meal: str
    mod_description: str


class DailyPrepSheet(BaseModel):
    """Comprehensive daily kitchen prep sheet."""

    date: str
    total_lunch: int = 0
    total_dinner: int = 0
    total_thalis: int = 0
    packing_labels: List[PackingLabel] = Field(default_factory=list)
    special_mods: List[SpecialMod] = Field(default_factory=list)
    late_orders: List[OrderEvent] = Field(default_factory=list)
    late_cancellations: List[OrderEvent] = Field(
        default_factory=list,
        description="Cancels that arrived after the cutoff. Shown as a pending "
        "reduction with a one-tap accept rather than silently applied.",
    )
    cancellations: List[OrderEvent] = Field(default_factory=list)
    unresolved_reviews: List[OrderEvent] = Field(default_factory=list)
    other_days: List[OrderEvent] = Field(default_factory=list)
    cook_names: List[str] = Field(
        default_factory=list,
        description="Display names of the cook. Her own messages are never counted.",
    )
    cook_message_count: int = Field(
        default=0, description="Messages from the cook that were skipped as her own."
    )
    late_cancellation_total: int = Field(
        default=0, description="Plates that late cancels would remove if accepted."
    )


class CustomerLedger(BaseModel):
    """Financial tracking per customer."""

    customer: str
    phone: Optional[str] = None
    total_orders: int = 0
    price_per_thali: Decimal = Decimal("80.00")
    total_billed: Decimal = Decimal("0.00")
    total_paid: Decimal = Decimal("0.00")
    total_claimed: Decimal = Decimal("0.00")
    total_refunded: Decimal = Decimal("0.00")
    balance_due: Decimal = Decimal("0.00")
    draft_reminder: str = ""
