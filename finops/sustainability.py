"""Sustainability economics — energy and carbon as governed cost levers (deck §11).

Region selection cuts $ and carbon together; reasoning queries are an energy bomb.
"""
from __future__ import annotations

# Grid carbon intensity (gCO2 / kWh) — illustrative 2026 snapshot.
REGION_CARBON = {
    "us-east-1": 380,
    "us-west-2": 120,   # Oregon hydro
    "europe-north1": 30,  # Norway
    "europe-central2": 660,  # Poland (dirtiest)
    "us-east-wa": 90,
}
# Electricity price (USD / kWh) — illustrative.
REGION_PRICE_KWH = {
    "us-east-1": 0.12,
    "us-west-2": 0.07,
    "europe-north1": 0.09,
    "europe-central2": 0.18,
    "us-east-wa": 0.055,
}

REASONING_ENERGY_MULTIPLIER = 80.0  # deck: reasoning ~74-86x a small-model query


def wh_per_query(total_tokens: int, wh_per_1k_tokens: float = 0.30, is_reasoning: bool = False) -> float:
    """Energy for one query. Median Gemini prompt ~0.24 Wh; reasoning ~74-86x."""
    base = (total_tokens / 1000.0) * wh_per_1k_tokens
    return base * (REASONING_ENERGY_MULTIPLIER if is_reasoning else 1.0)


def carbon_g(wh: float, region: str = "us-east-1") -> float:
    """Grams CO2 for an energy amount in a region."""
    gco2_kwh = REGION_CARBON.get(region, 400)
    return (wh / 1000.0) * gco2_kwh


def energy_cost_usd(wh: float, region: str = "us-east-1") -> float:
    """Electricity cost of an energy amount in a region."""
    return (wh / 1000.0) * REGION_PRICE_KWH.get(region, 0.12)


def tokens_per_watt(total_tokens: int, wh: float, seconds: float = 1.0) -> float:
    """Energy efficiency of serving: tokens per watt (higher is better)."""
    watts = (wh * 3600.0) / seconds if seconds > 0 else 0.0
    return total_tokens / watts if watts > 0 else 0.0


def region_comparison_table(kwh: float) -> list[dict]:
    """Compare carbon emissions and electricity cost across all 5 monitored regions (Extension 5)."""
    wh = kwh * 1000.0
    rows = []
    for reg, gco2 in REGION_CARBON.items():
        price = REGION_PRICE_KWH.get(reg, 0.12)
        carb_kg = (kwh * gco2) / 1000.0
        elec_usd = kwh * price
        rows.append({
            "region": reg,
            "carbon_intensity_gco2_kwh": gco2,
            "price_usd_kwh": price,
            "total_carbon_kg": round(carb_kg, 2),
            "total_elec_usd": round(elec_usd, 2),
        })
    return sorted(rows, key=lambda x: x["total_carbon_kg"])


def carbon_aware_workload_savings(
    total_kwh: float,
    baseline_region: str = "us-east-1",
    target_region: str = "europe-north1",
) -> dict:
    """Calculate emissions and energy cost reduction from migrating workloads (Extension 5)."""
    wh = total_kwh * 1000.0
    base_carb = carbon_g(wh, baseline_region) / 1000.0  # kg
    target_carb = carbon_g(wh, target_region) / 1000.0  # kg
    base_cost = energy_cost_usd(wh, baseline_region)
    target_cost = energy_cost_usd(wh, target_region)

    carbon_saved_kg = base_carb - target_carb
    carbon_saved_pct = (carbon_saved_kg / base_carb * 100.0) if base_carb > 0 else 0.0
    cost_saved_usd = base_cost - target_cost
    cost_saved_pct = (cost_saved_usd / base_cost * 100.0) if base_cost > 0 else 0.0

    return {
        "baseline_region": baseline_region,
        "target_region": target_region,
        "total_kwh": round(total_kwh, 2),
        "baseline_carbon_kg": round(base_carb, 2),
        "target_carbon_kg": round(target_carb, 2),
        "carbon_saved_kg": round(carbon_saved_kg, 2),
        "carbon_saved_pct": round(carbon_saved_pct, 1),
        "baseline_energy_cost_usd": round(base_cost, 2),
        "target_energy_cost_usd": round(target_cost, 2),
        "cost_saved_usd": round(cost_saved_usd, 2),
        "cost_saved_pct": round(cost_saved_pct, 1),
    }
