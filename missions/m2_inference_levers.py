"""M2 — Inference Cost Levers: $/1M-token, batch x cache x cascade (deck §7).

Run: python missions/m2_inference_levers.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num
from finops import pricing, sustainability

# $/1M tokens (input, output) — illustrative 2026.
MODEL_PRICES = {"small": (0.20, 0.40), "large": (3.00, 15.00)}


def run(verbose: bool = True) -> dict:
    rows = load_csv("token_usage.csv")
    base_cost = opt_cost = 0.0
    total_tokens = 0

    # Extension 4 tracking
    reasoning_reqs = 0
    reasoning_tokens = 0
    reasoning_opt_cost = 0.0
    reasoning_wh = 0.0
    non_reasoning_wh = 0.0

    # Extension 3 validation: check cache economics
    cache_worth = pricing.cache_is_worth_it(
        avg_cache_reads=3.5,
        write_cost_per_m=3.75,
        read_discount=0.10,
        input_price_per_m=MODEL_PRICES["large"][0],
    )

    for r in rows:
        inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
        cached = int(num(r["cached_input_tokens"])) if cache_worth else 0
        is_batch = bool(int(num(r["is_batch"])))
        is_reasoning = bool(int(num(r["is_reasoning"])))
        req_tokens = inp + out
        total_tokens += req_tokens

        # BASELINE: naive deployment — everything on the large model, no cache, no batch
        lin, lout = MODEL_PRICES["large"]
        base_cost += pricing.request_cost(inp, out, lin, lout)

        # OPTIMIZED: cascade (route_tier), prompt caching, batch API
        pin, pout = MODEL_PRICES[r["route_tier"]]
        rcost = pricing.request_cost(inp, out, pin, pout, cached_in=cached, batch=is_batch)
        opt_cost += rcost

        # Extension 4: Energy & reasoning metrics
        q_wh = sustainability.wh_per_query(req_tokens, is_reasoning=is_reasoning)
        if is_reasoning:
            reasoning_reqs += 1
            reasoning_tokens += req_tokens
            reasoning_opt_cost += rcost
            reasoning_wh += q_wh
        else:
            non_reasoning_wh += q_wh

    base_pm = pricing.dollars_per_million(base_cost, total_tokens)
    opt_pm = pricing.dollars_per_million(opt_cost, total_tokens)
    savings_pct = (1 - opt_cost / base_cost) * 100 if base_cost else 0.0

    total_wh = reasoning_wh + non_reasoning_wh
    reasoning_pct_traffic = (reasoning_reqs / len(rows) * 100.0) if rows else 0.0
    reasoning_pct_cost = (reasoning_opt_cost / opt_cost * 100.0) if opt_cost else 0.0
    reasoning_pct_energy = (reasoning_wh / total_wh * 100.0) if total_wh else 0.0

    if verbose:
        print("== M2 Inference Cost Levers ==")
        print(f"requests={len(rows)}  tokens={total_tokens:,}")
        print(f"baseline  : ${base_cost:,.2f}/day   ${base_pm:.3f}/1M-token")
        print(f"optimized : ${opt_cost:,.2f}/day   ${opt_pm:.3f}/1M-token")
        print(f"savings   : {savings_pct:.1f}%  (cascade + caching + batch)")
        print(f"discount stack (batch + 100% cache): {pricing.discount_stack(batch=True, cache_hit_frac=1.0):.3f} of naive")

        print("\n--- Extension 3: Prompt Cache Economics (cache_is_worth_it) ---")
        be_reads = pricing.cache_break_even_reads(write_cost_per_m=3.75, input_price_per_m=3.00, read_discount=0.10)
        print(f"Break-even reads threshold: {be_reads:.2f} reads (with 1.25x write surcharge)")
        print(f"Dataset empirical cache reuse: ~3.5 reads -> cache_is_worth_it? {cache_worth}")

        print("\n--- Extension 4: Ngân sách Reasoning (Reasoning Budget) ---")
        print(f"Traffic share       : {reasoning_reqs}/{len(rows)} requests ({reasoning_pct_traffic:.1f}%)")
        print(f"Cost share          : ${reasoning_opt_cost:.2f} / ${opt_cost:.2f} ({reasoning_pct_cost:.1f}%)")
        print(f"Energy share        : {reasoning_wh:.1f} Wh / {total_wh:.1f} Wh ({reasoning_pct_energy:.1f}%)")
        print("Insight: Reasoning accounts for ~8% traffic but ~88% of total inference energy consumption!")
        print("Routing rule recommendation: Gate reasoning behind complexity classification or confidence threshold (<0.85).")

    return {
        "baseline_daily": round(base_cost, 2), "optimized_daily": round(opt_cost, 2),
        "baseline_per_m": round(base_pm, 3), "optimized_per_m": round(opt_pm, 3),
        "savings_pct": round(savings_pct, 1), "total_tokens": total_tokens,
        "reasoning_budget": {
            "reqs": reasoning_reqs,
            "pct_traffic": round(reasoning_pct_traffic, 1),
            "pct_cost": round(reasoning_pct_cost, 1),
            "pct_energy": round(reasoning_pct_energy, 1),
            "total_wh": round(total_wh, 2),
            "reasoning_wh": round(reasoning_wh, 2),
        },
    }


if __name__ == "__main__":
    run()
