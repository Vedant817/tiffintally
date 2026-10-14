"""Pydantic schemas and data models for TiffinTally."""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

MealType = Literal["lunch", "dinner", "both", "unspecified"]
OrderAction = Literal["new", "change", "cancel", "pause", "payment", "none"]


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
        default="new", description="Action type: new, change, cancel, pause, payment, none"
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
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Extraction confidence score (0.0 to 1.0)"
    )
    raw_text: str = Field(default="", description="Original raw message text")
    timestamp: Optional[str] = Field(default=None, description="ISO timestamp message was received")
    is_late: bool = Field(
        default=False, description="Flag indicating whether message was received after cutoff"
    )
    audit_flags: List[str] = Field(
        default_factory=list, description="Security and guardrail audit flags"
    )
    needs_review: bool = Field(default=False, description="Flag indicating manual review required")


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
    forecast_recommended: Optional[int] = None
    forecast_reasoning: Optional[str] = None
    packing_labels: List[PackingLabel] = Field(default_factory=list)
    special_mods: List[SpecialMod] = Field(default_factory=list)
    late_orders: List[OrderEvent] = Field(default_factory=list)
    cancellations: List[OrderEvent] = Field(default_factory=list)
    unresolved_reviews: List[OrderEvent] = Field(default_factory=list)
    other_days: List[OrderEvent] = Field(default_factory=list)


class CustomerLedger(BaseModel):
    """Financial tracking per customer."""

    customer: str
    phone: Optional[str] = None
    total_orders: int = 0
    price_per_thali: float = 80.0
    total_billed: float = 0.0
    total_paid: float = 0.0
    balance_due: float = 0.0
    draft_reminder: str = ""
