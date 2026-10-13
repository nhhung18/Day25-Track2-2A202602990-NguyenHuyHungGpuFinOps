"""Pricing & purchasing economics — measure in $/1M-token, not $/GPU-hr.

Figures are June-2026 as-of snapshots from the deck's RESEARCH dossier; treat
live prices as fast-moving (re-baseline before each cohort).
"""
from __future__ import annotations


def request_cost(
    input_tok: int,
    output_tok: int,
    price_in_per_m: float,
    price_out_per_m: float,
    cached_in: int = 0,
    cache_discount: float = 0.10,   # Anthropic cached-read ~0.1x (=-90%)
    batch: bool = False,
    batch_discount: float = 0.50,   # Batch API ~ -50%
) -> float:
    """USD cost of a single request. Cached input billed at cache_discount x price."""
    cached_in = min(max(0, cached_in), input_tok)
    uncached_in = input_tok - cached_in
    cost = (
        (uncached_in / 1e6) * price_in_per_m
        + (cached_in / 1e6) * price_in_per_m * cache_discount
        + (output_tok / 1e6) * price_out_per_m
    )
    if batch:
        cost *= batch_discount
    return cost


def dollars_per_million(total_cost_usd: float, total_tokens: int) -> float:
    """Aggregate unit economics: $ per 1,000,000 tokens served."""
    if total_tokens <= 0:
        return 0.0
    return total_cost_usd / (total_tokens / 1e6)


def discount_stack(
    batch: bool = False,
    cache_hit_frac: float = 0.0,
    batch_discount: float = 0.50,
    cache_discount: float = 0.10,
) -> float:
    """Effective fraction of the naive bill after stacking discounts (input-heavy view).

    Discounts MULTIPLY: cache applies to the cached share of input, batch to the
    whole bill. batch + 100% cache-hit -> 0.5 * 0.1 = 0.05 (~95% off).
    """
    cache_mult = cache_hit_frac * cache_discount + (1.0 - cache_hit_frac)
    batch_mult = batch_discount if batch else 1.0
    return cache_mult * batch_mult


def break_even_utilization(discount_frac: float) -> float:
    """Utilization at which a commitment pays off ~= 1 - discount.

    A 45% reserved discount needs ~55% utilization (~13.2h/day) to beat on-demand.
    """
    return max(0.0, min(1.0, 1.0 - discount_frac))


# Illustrative hourly spot interruption rates by GPU architecture (deck §4)
GPU_INTERRUPTION_RATES = {
    "H100": 0.03,    # High-tier, tightly managed clusters
    "H200": 0.04,
    "A100": 0.05,
    "A10G": 0.12,    # Commodity inference tier, higher eviction
    "L4": 0.15,      # High spot turnover
    "B200": 0.02,
    "MI300X": 0.05,
}


def recommend_tier(
    hours_per_day: float,
    interruptible: bool,
    reserved_discount: float = 0.45,
    gpu_type: str | None = None,
    job_days: int | None = None,
) -> str:
    """Pick a purchasing tier from a workload's duty cycle + interruptibility.

    Baseline policy (verified by tests):
      - interruptible & not 24/7  -> 'spot'      (checkpoint and ride the discount)
      - duty cycle >= break-even  -> 'reserved'  (steady, high utilization)
      - otherwise                 -> 'on_demand' (spiky / low duty)

    Enhanced considerations (Your Turn Extension 1):
      - When gpu_type is supplied, high spot interruption rates (>10%) on long training
        jobs can make rework eat into spot savings.
      - When job_days is supplied, short commitments (<30 days) on non-interruptible
        workloads without cluster pooling may favor on-demand over multi-year lock-in.
    """
    duty = max(0.0, hours_per_day) / 24.0
    be = break_even_utilization(reserved_discount)

    if interruptible and hours_per_day < 24:
        # Check if excessive interruption rate makes spot unviable
        ir = GPU_INTERRUPTION_RATES.get(gpu_type or "", 0.05)
        if ir > 0.30 and hours_per_day > 16:
            # Extreme interruption penalty fallback
            return "reserved" if duty >= be else "on_demand"
        return "spot"

    if duty >= be:
        return "reserved"
    return "on_demand"


def recommend_tier_matrix(
    hours_per_day: float,
    interruptible: bool,
    gpu_type: str = "H100",
    job_days: int = 30,
    reserved_3yr_discount: float = 0.45,
    reserved_1yr_discount: float = 0.20,
) -> dict:
    """Decision matrix for Extension 1 evaluating all three commitment tiers."""
    duty = max(0.0, hours_per_day) / 24.0
    be_3yr = break_even_utilization(reserved_3yr_discount)
    be_1yr = break_even_utilization(reserved_1yr_discount)
    ir = GPU_INTERRUPTION_RATES.get(gpu_type, 0.05)

    base_rec = recommend_tier(hours_per_day, interruptible, reserved_3yr_discount, gpu_type, job_days)

    return {
        "recommended_tier": base_rec,
        "duty_cycle": round(duty, 3),
        "break_even_3yr": round(be_3yr, 3),
        "break_even_1yr": round(be_1yr, 3),
        "interruption_rate": ir,
        "suitable_for_1yr_reserved": duty >= be_1yr and not interruptible,
        "suitable_for_3yr_reserved": duty >= be_3yr and not interruptible,
    }


def cache_break_even_reads(
    write_cost_per_m: float,
    input_price_per_m: float = 3.0,
    read_discount: float = 0.10,
) -> float:
    """Calculate the minimum number of cache reads needed to break even (Extension 3).

    Formula:
      Net savings per read = input_price_per_m * (1 - read_discount)
      Break-even reads = write_cost_per_m / Net savings per read
    """
    net_savings_per_read = input_price_per_m * (1.0 - read_discount)
    if net_savings_per_read <= 0:
        return float("inf")
    return write_cost_per_m / net_savings_per_read


def cache_is_worth_it(
    avg_cache_reads: float,
    write_cost_per_m: float,
    read_discount: float = 0.10,
    input_price_per_m: float = 3.0,
) -> bool:
    """Determine whether prompt caching saves money given average read reuse (Extension 3).

    Cache is financially worth it when:
      avg_cache_reads * input_price_per_m * (1 - read_discount) > write_cost_per_m
    """
    be_reads = cache_break_even_reads(write_cost_per_m, input_price_per_m, read_discount)
    return avg_cache_reads >= be_reads


def spot_checkpoint_cost(
    job_hours: float,
    spot_hr: float,
    on_demand_hr: float,
    interrupt_rate: float = 0.05,      # per-hour chance (H100 spot ~<5%)
    ckpt_overhead_frac: float = 0.03,  # steady cost of writing checkpoints
    rework_hours_per_interrupt: float = 0.5,
) -> dict:
    """Effective cost of running a checkpointable job on spot vs on-demand.

    Interruptions waste the compute since the last checkpoint (rework); checkpointing
    adds a small steady overhead. Spot still wins for interruptible jobs.
    """
    expected_interrupts = job_hours * interrupt_rate
    rework_hours = expected_interrupts * rework_hours_per_interrupt
    effective_hours = job_hours * (1.0 + ckpt_overhead_frac) + rework_hours
    spot_cost = effective_hours * spot_hr
    on_demand_cost = job_hours * on_demand_hr
    savings_pct = (1.0 - spot_cost / on_demand_cost) * 100.0 if on_demand_cost > 0 else 0.0
    return {
        "spot_effective_hours": round(effective_hours, 2),
        "spot_cost": round(spot_cost, 2),
        "on_demand_cost": round(on_demand_cost, 2),
        "savings_pct": round(savings_pct, 1),
    }
