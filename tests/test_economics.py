"""Tests for kitchen economics, BOM calculator, and AI inference unit economics."""

from tiffintally.economics import KitchenEconomics


def test_bom_calculation():
    econ = KitchenEconomics()
    bom = econ.compute_bom(total_thalis=40)
    assert bom.total_thalis == 40
    assert len(bom.groceries) == 6
    # 40 * 0.075 = 3.0 kg atta
    atta_item = next(g for g in bom.groceries if "Atta" in g.name)
    assert atta_item.quantity == 3.0
    # Cost per plate should be realistic (~30 to 45 INR)
    assert 25.0 <= bom.cost_per_plate <= 50.0
    assert bom.total_raw_material_cost > 0


def test_bom_zero_thalis():
    econ = KitchenEconomics()
    bom = econ.compute_bom(total_thalis=0)
    assert bom.total_thalis == 0
    assert bom.total_raw_material_cost == 0.0
    assert len(bom.groceries) == 0


def test_ai_unit_economics():
    econ = KitchenEconomics()
    comp = econ.compute_ai_unit_economics(daily_messages=50)
    assert comp.daily_messages == 50
    assert comp.gpt4o_monthly_cost_inr > 0
    assert comp.open_slm_monthly_cost_inr == 0.0
    assert comp.monthly_savings_inr == comp.gpt4o_monthly_cost_inr
    assert "100% Local" in comp.privacy_guarantee


def test_waste_reduction_roi():
    econ = KitchenEconomics()
    roi = econ.compute_waste_reduction_roi(daily_confirmed_plates=40)
    assert roi.daily_waste_plates_saved > 3.0
    assert roi.monthly_waste_cost_saved_inr > 3500.0
    assert roi.annual_waste_cost_saved_inr > 40000.0
