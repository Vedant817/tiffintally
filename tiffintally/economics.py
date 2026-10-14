"""
Production kitchen economics, Bill of Materials (BOM) grocery forecasting,
and AI inference unit economics analysis for TiffinTally.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class GroceryItem:
    name: str
    quantity: float
    unit: str
    est_cost_inr: float


@dataclass
class KitchenBOM:
    """Bill of Materials for daily kitchen preparation."""

    total_thalis: int
    groceries: List[GroceryItem]
    total_raw_material_cost: float
    cost_per_plate: float


@dataclass
class EconomicComparison:
    """Comparative unit economics: Proprietary Cloud API vs Open-Weight Edge SLM."""

    daily_messages: int
    gpt4o_monthly_cost_inr: float
    gpt4o_cost_per_order_inr: float
    open_slm_monthly_cost_inr: float
    open_slm_cost_per_order_inr: float
    monthly_savings_inr: float
    privacy_guarantee: str


@dataclass
class FoodWasteROI:
    """Quantified food waste reduction via TabPFN probabilistic demand forecasting."""

    daily_plates: int
    uncalibrated_waste_plates_per_day: float
    tabpfn_waste_plates_per_day: float
    daily_waste_plates_saved: float
    cost_per_plate_inr: float
    monthly_waste_cost_saved_inr: float
    annual_waste_cost_saved_inr: float


class KitchenEconomics:
    """
    Computes real-world domestic kitchen economics:
    - Standard Indian thali recipe bill of materials (3 rotis, 1 dal, 1 sabzi, rice, salad)
    - TabPFN waste mitigation ROI
    - SLM edge inference vs Big Tech cloud API unit economics
    """

    # Recipe breakdown per single standard thali (in grams / kg / units)
    ATTA_PER_THALI_KG = 0.075  # 75g atta = 3 rotis
    DAL_PER_THALI_KG = 0.040  # 40g raw pulses
    VEGETABLES_PER_THALI_KG = 0.150  # 150g mixed seasonal vegetables
    RICE_PER_THALI_KG = 0.060  # 60g raw basmati/kolam rice
    OIL_SPICES_PER_THALI_INR = 7.0  # ₹7 spices, oil, tadka
    PACKAGING_BOX_INR = 5.0  # ₹5 3-compartment CPET container

    # Current grocery market prices in Pune / Tier-1 Indian cities (INR / kg)
    PRICE_ATTA_PER_KG = 42.0
    PRICE_DAL_PER_KG = 140.0
    PRICE_VEG_PER_KG = 45.0
    PRICE_RICE_PER_KG = 60.0

    SELLING_PRICE_PER_THALI = 80.0

    def compute_bom(self, total_thalis: int) -> KitchenBOM:
        """Calculate grocery requirements and raw material expenditure for planned thalis."""
        if total_thalis <= 0:
            return KitchenBOM(
                total_thalis=0,
                groceries=[],
                total_raw_material_cost=0.0,
                cost_per_plate=0.0,
            )

        atta_kg = round(total_thalis * self.ATTA_PER_THALI_KG, 2)
        atta_cost = round(atta_kg * self.PRICE_ATTA_PER_KG, 2)

        dal_kg = round(total_thalis * self.DAL_PER_THALI_KG, 2)
        dal_cost = round(dal_kg * self.PRICE_DAL_PER_KG, 2)

        veg_kg = round(total_thalis * self.VEGETABLES_PER_THALI_KG, 2)
        veg_cost = round(veg_kg * self.PRICE_VEG_PER_KG, 2)

        rice_kg = round(total_thalis * self.RICE_PER_THALI_KG, 2)
        rice_cost = round(rice_kg * self.PRICE_RICE_PER_KG, 2)

        oil_spices_cost = round(total_thalis * self.OIL_SPICES_PER_THALI_INR, 2)
        packaging_cost = round(total_thalis * self.PACKAGING_BOX_INR, 2)

        groceries = [
            GroceryItem("Wheat Atta (3 rotis/thali)", atta_kg, "kg", atta_cost),
            GroceryItem("Dal / Pulses (Toor/Moong)", dal_kg, "kg", dal_cost),
            GroceryItem("Seasonal Vegetables", veg_kg, "kg", veg_cost),
            GroceryItem("Rice (Kolam/Sona Masoori)", rice_kg, "kg", rice_cost),
            GroceryItem("Cooking Oil, Ghee & Spices", total_thalis, "servings", oil_spices_cost),
            GroceryItem("Eco Packaging Containers", total_thalis, "units", packaging_cost),
        ]

        total_cost = round(
            atta_cost + dal_cost + veg_cost + rice_cost + oil_spices_cost + packaging_cost, 2
        )
        cost_per_plate = round(total_cost / total_thalis, 2)

        return KitchenBOM(
            total_thalis=total_thalis,
            groceries=groceries,
            total_raw_material_cost=total_cost,
            cost_per_plate=cost_per_plate,
        )

    def compute_ai_unit_economics(self, daily_messages: int = 50) -> EconomicComparison:
        """
        Compare monthly cost of running proprietary cloud LLMs (GPT-4o)
        versus our Edge Fine-Tuned SLM (Qwen2.5-0.5B).
        """
        days_per_month = 30
        monthly_messages = daily_messages * days_per_month

        # GPT-4o pricing: $2.50 / 1M input tokens, $10.00 / 1M output tokens (approx ₹84 / USD)
        # Average WhatsApp order message: 350 prompt tokens (with system rules), 80 response tokens
        cost_per_call_usd = (350 / 1_000_000 * 2.50) + (80 / 1_000_000 * 10.00)
        cost_per_call_inr = cost_per_call_usd * 84.0
        gpt4o_monthly_inr = round(monthly_messages * cost_per_call_inr, 2)

        # Open SLM: Local CPU/NPU inference on Raspberry Pi 5 or zero-cost serverless free tier
        open_slm_monthly_inr = 0.0
        open_slm_cost_per_call_inr = 0.0

        savings = round(gpt4o_monthly_inr - open_slm_monthly_inr, 2)

        return EconomicComparison(
            daily_messages=daily_messages,
            gpt4o_monthly_cost_inr=gpt4o_monthly_inr,
            gpt4o_cost_per_order_inr=round(cost_per_call_inr, 3),
            open_slm_monthly_cost_inr=open_slm_monthly_inr,
            open_slm_cost_per_order_inr=open_slm_cost_per_call_inr,
            monthly_savings_inr=savings,
            privacy_guarantee=(
                "Not a measured zero-leakage guarantee. "
                "Hosted calls replace names with tokens when a key is set."
            ),
        )

    def compute_waste_reduction_roi(
        self, daily_confirmed_plates: int = 40, raw_cost_per_plate: float = 38.0
    ) -> FoodWasteROI:
        """
        Illustrative arithmetic only. The 4.5 and 0.8 plate figures are assumptions,
        not a measurement from this kitchen or from TabPFN.
        """
        uncalibrated_waste = 4.5  # average plates discarded or sold at heavy loss
        tabpfn_waste = 0.8  # calibrated dynamic buffer
        saved_plates = uncalibrated_waste - tabpfn_waste

        daily_saved_inr = round(saved_plates * raw_cost_per_plate, 2)
        monthly_saved_inr = round(daily_saved_inr * 30, 2)
        annual_saved_inr = round(monthly_saved_inr * 12, 2)

        return FoodWasteROI(
            daily_plates=daily_confirmed_plates,
            uncalibrated_waste_plates_per_day=uncalibrated_waste,
            tabpfn_waste_plates_per_day=tabpfn_waste,
            daily_waste_plates_saved=saved_plates,
            cost_per_plate_inr=raw_cost_per_plate,
            monthly_waste_cost_saved_inr=monthly_saved_inr,
            annual_waste_cost_saved_inr=annual_saved_inr,
        )
