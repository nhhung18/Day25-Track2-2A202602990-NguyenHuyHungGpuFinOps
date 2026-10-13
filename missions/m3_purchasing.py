"""M3 — Purchasing Strategy: break-even, tier choice, spot-checkpoint sim (deck §4).

Run: python missions/m3_purchasing.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num, catalog_by_type
from finops import pricing, sustainability

DAYS = 30


def run(verbose: bool = True) -> dict:
    jobs = load_csv("workloads.csv")
    cat = catalog_by_type()
    on_demand_monthly = optimized_monthly = 0.0
    recs = []

    # Extension 5 tracking: interruptible jobs power and energy
    interruptible_kwh = 0.0

    for j in jobs:
        gtype = j["gpu_type"]
        ngpu = int(num(j["num_gpus"]))
        hpd = num(j["hours_per_day"])
        days = int(num(j["days"]))
        interruptible = bool(int(num(j["interruptible"])))
        c = cat[gtype]
        gpu_hours = hpd * DAYS * ngpu
        od = num(c["on_demand_hr"])
        on_demand_cost = gpu_hours * od

        # Extension 1: Tier recommendation
        tier = pricing.recommend_tier(hpd, interruptible, gpu_type=gtype, job_days=days)
        if tier == "spot":
            sim = pricing.spot_checkpoint_cost(gpu_hours, num(c["spot_hr"]), od)
            opt_cost = sim["spot_cost"]
        elif tier == "reserved":
            opt_cost = gpu_hours * num(c["reserved_3yr_hr"])
        else:
            opt_cost = on_demand_cost

        on_demand_monthly += on_demand_cost
        optimized_monthly += opt_cost
        recs.append({"job_id": j["job_id"], "gpu_type": gtype, "tier": tier,
                     "on_demand": round(on_demand_cost), "optimized": round(opt_cost)})

        if interruptible:
            job_watts = num(c["watts"]) * ngpu
            actual_gpu_hours = hpd * days * ngpu
            interruptible_kwh += (job_watts * actual_gpu_hours) / 1000.0

    savings = on_demand_monthly - optimized_monthly
    savings_pct = savings / on_demand_monthly * 100 if on_demand_monthly else 0.0

    # Extension 5: Carbon-aware migration analysis
    carbon_comparison = sustainability.carbon_aware_workload_savings(
        interruptible_kwh, baseline_region="us-east-1", target_region="europe-north1"
    )
    all_regions = sustainability.region_comparison_table(interruptible_kwh)

    if verbose:
        print("== M3 Purchasing Strategy ==")
        print(f"break-even utilization @ 45% reserved discount = {pricing.break_even_utilization(0.45):.0%}")
        print(f"{'job':18}{'gpu':7}{'tier':11}{'on-demand':>12}{'optimized':>12}")
        for r in recs:
            print(f"{r['job_id']:18}{r['gpu_type']:7}{r['tier']:11}${r['on_demand']:>11,}${r['optimized']:>11,}")
        print(f"\nmonthly: on-demand ${on_demand_monthly:,.0f} -> optimized ${optimized_monthly:,.0f}  ({savings_pct:.1f}% saved)")

        print("\n--- Extension 1: Decision Matrix (Interruption Risk & Commitment Term) ---")
        for j in jobs:
            hpd = num(j["hours_per_day"])
            intrp = bool(int(num(j["interruptible"])))
            mat = pricing.recommend_tier_matrix(hpd, intrp, gpu_type=j["gpu_type"], job_days=int(num(j["days"])))
            print(f"  {j['job_id']:18} duty={mat['duty_cycle']:.0%} | spot_risk={mat['interruption_rate']:.0%} | 1yr_ok={mat['suitable_for_1yr_reserved']} | tier={mat['recommended_tier']}")

        print("\n--- Extension 5: Carbon-Aware Scheduling (Interruptible Jobs) ---")
        print(f"Total energy for interruptible batch/train jobs: {interruptible_kwh:,.1f} kWh")
        print(f"{'Region':18}{'gCO2/kWh':>10}{'$/kWh':>8}{'Total CO2 (kg)':>16}{'Elec Cost ($)':>14}")
        for reg in all_regions:
            print(f"{reg['region']:18}{reg['carbon_intensity_gco2_kwh']:>10}{reg['price_usd_kwh']:>8.3f}{reg['total_carbon_kg']:>16.1f}${reg['total_elec_usd']:>13.2f}")
        print(f"\nMigrating from us-east-1 to europe-north1 (hydro clean):")
        print(f"  Carbon reduction: {carbon_comparison['carbon_saved_kg']} kg CO2e saved ({carbon_comparison['carbon_saved_pct']}%)")
        print(f"  Electricity bill: ${carbon_comparison['cost_saved_usd']} saved ({carbon_comparison['cost_saved_pct']}%)")
        print("Latency trade-off: Interruptible batch jobs have no real-time latency SLA, making global geo-shifting optimal.")

    return {
        "recommendations": recs,
        "on_demand_monthly": round(on_demand_monthly),
        "optimized_monthly": round(optimized_monthly),
        "savings_pct": round(savings_pct, 1),
        "carbon_comparison": carbon_comparison,
        "all_regions": all_regions,
    }


if __name__ == "__main__":
    run()
