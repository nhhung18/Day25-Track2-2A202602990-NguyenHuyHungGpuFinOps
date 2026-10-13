import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from finops import pricing, metrics, sustainability


def test_extension1_recommend_tier_matrix():
    """Extension 1: Test tier recommendations with interruption rates and commitment terms."""
    mat_h100 = pricing.recommend_tier_matrix(20, True, gpu_type="H100", job_days=14)
    assert mat_h100["recommended_tier"] == "spot"
    assert mat_h100["interruption_rate"] == 0.03
    assert abs(mat_h100["duty_cycle"] - (20 / 24)) < 1e-3

    mat_infer = pricing.recommend_tier_matrix(24, False, gpu_type="A100", job_days=30)
    assert mat_infer["recommended_tier"] == "reserved"
    assert mat_infer["suitable_for_3yr_reserved"] is True

    # Standard compatibility check
    assert pricing.recommend_tier(2, True) == "spot"
    assert pricing.recommend_tier(24, False) == "reserved"
    assert pricing.recommend_tier(4, False) == "on_demand"


def test_extension2_mbu_and_vram_metrics():
    """Extension 2: Test $/GB-VRAM and $/TB/s bandwidth economics."""
    # H100: $2.50/hr, 80GB VRAM, 3.35 TB/s
    cost_per_gb = metrics.vram_cost_efficiency(2.50, 80.0)
    cost_per_bw = metrics.bandwidth_cost_efficiency(2.50, 3.35)
    assert abs(cost_per_gb - (2.50 / 80.0)) < 1e-5
    assert abs(cost_per_bw - (2.50 / 3.35)) < 1e-5

    # L4: $0.80/hr, 24GB VRAM, 0.30 TB/s
    l4_bw_cost = metrics.bandwidth_cost_efficiency(0.80, 0.30)
    # L4 bandwidth cost per TB/s-hr ($2.67) is higher than H100 ($0.75)
    assert l4_bw_cost > cost_per_bw


def test_extension3_cache_is_worth_it():
    """Extension 3: Test cache_is_worth_it and break-even read calculation."""
    # Base input: $3.00/M, Read discount: 10% (90% off), Write cost: $3.75/M (1.25x)
    # Savings per read = $3.00 * (1 - 0.10) = $2.70/M
    # Break-even reads = 3.75 / 2.70 = 1.3888...
    be = pricing.cache_break_even_reads(write_cost_per_m=3.75, input_price_per_m=3.0, read_discount=0.10)
    assert abs(be - 1.38888) < 1e-3

    # If reads >= break-even -> True, else False
    assert pricing.cache_is_worth_it(avg_cache_reads=2.0, write_cost_per_m=3.75, read_discount=0.10, input_price_per_m=3.0) is True
    assert pricing.cache_is_worth_it(avg_cache_reads=1.0, write_cost_per_m=3.75, read_discount=0.10, input_price_per_m=3.0) is False
    assert pricing.cache_is_worth_it(avg_cache_reads=3.5, write_cost_per_m=3.75, read_discount=0.10) is True


def test_extension4_reasoning_energy_scaling():
    """Extension 4: Test reasoning energy multiplier."""
    base_wh = sustainability.wh_per_query(1000, wh_per_1k_tokens=0.30, is_reasoning=False)
    reasoning_wh = sustainability.wh_per_query(1000, wh_per_1k_tokens=0.30, is_reasoning=True)
    assert abs(reasoning_wh - base_wh * sustainability.REASONING_ENERGY_MULTIPLIER) < 1e-5
    assert reasoning_wh > base_wh * 70  # ~80x


def test_extension5_carbon_aware_savings():
    """Extension 5: Test multi-region carbon & electricity economics."""
    kwh = 1000.0  # 1,000 kWh
    comparison = sustainability.carbon_aware_workload_savings(kwh, "us-east-1", "europe-north1")
    assert comparison["baseline_carbon_kg"] == 380.0
    assert comparison["target_carbon_kg"] == 30.0
    assert comparison["carbon_saved_kg"] == 350.0
    assert abs(comparison["carbon_saved_pct"] - 92.1) < 0.1

    table = sustainability.region_comparison_table(kwh)
    assert len(table) == 5
    # europe-north1 should be cleanest
    assert table[0]["region"] == "europe-north1"

