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
CACHE_WRITE_COST_FRAC = 0.25
CACHE_READ_DISCOUNT = 0.10


def _cache_economics(rows: list[dict]) -> dict:
    """Estimate cache read reuse by route tier from deterministic token logs."""
    by_tier = {}
    for tier, (price_in, _) in MODEL_PRICES.items():
        tier_rows = [r for r in rows if r["route_tier"] == tier]
        cached_rows = [r for r in tier_rows if int(num(r["cached_input_tokens"])) > 0]
        prefixes = {
            (r["team"], r["project"], r["route_tier"])
            for r in cached_rows
        }
        avg_reads = len(cached_rows) / max(len(prefixes), 1)
        write_cost = price_in * CACHE_WRITE_COST_FRAC
        break_even = pricing.cache_break_even_reads(
            write_cost_per_m=write_cost,
            input_price_per_m=price_in,
            read_discount=CACHE_READ_DISCOUNT,
        )
        by_tier[tier] = {
            "avg_cache_reads": round(avg_reads, 1),
            "break_even_reads": round(break_even, 2),
            "cache_worth_it": pricing.cache_is_worth_it(
                avg_cache_reads=avg_reads,
                write_cost_per_m=write_cost,
                input_price_per_m=price_in,
                read_discount=CACHE_READ_DISCOUNT,
            ),
        }
    return by_tier


def run(verbose: bool = True) -> dict:
    rows = load_csv("token_usage.csv")
    cache_policy = _cache_economics(rows)
    base_cost = opt_cost = 0.0
    cost_by_reasoning = {True: 0.0, False: 0.0}
    tokens_by_reasoning = {True: 0, False: 0}
    wh_by_reasoning = {True: 0.0, False: 0.0}
    total_tokens = 0
    for r in rows:
        inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
        tier = r["route_tier"]
        cached = int(num(r["cached_input_tokens"])) if cache_policy[tier]["cache_worth_it"] else 0
        is_batch = bool(int(num(r["is_batch"])))
        is_reasoning = bool(int(num(r["is_reasoning"])))
        total_tokens += inp + out
        # BASELINE: naive deployment — everything on the large model, no cache, no batch
        lin, lout = MODEL_PRICES["large"]
        base_cost += pricing.request_cost(inp, out, lin, lout)
        # OPTIMIZED: cascade (route_tier), prompt caching, batch API
        pin, pout = MODEL_PRICES[tier]
        req_cost = pricing.request_cost(inp, out, pin, pout, cached_in=cached, batch=is_batch)
        opt_cost += req_cost
        cost_by_reasoning[is_reasoning] += req_cost
        tokens_by_reasoning[is_reasoning] += inp + out
        wh_by_reasoning[is_reasoning] += sustainability.wh_per_query(inp + out, is_reasoning=is_reasoning)

    base_pm = pricing.dollars_per_million(base_cost, total_tokens)
    opt_pm = pricing.dollars_per_million(opt_cost, total_tokens)
    savings_pct = (1 - opt_cost / base_cost) * 100 if base_cost else 0.0
    reasoning_requests = sum(1 for r in rows if int(num(r["is_reasoning"])))
    reasoning_cost_pct = cost_by_reasoning[True] / opt_cost * 100 if opt_cost else 0.0
    reasoning_traffic_pct = reasoning_requests / len(rows) * 100 if rows else 0.0
    target_reasoning_pct = 5.0
    excess_factor = max(0.0, 1.0 - target_reasoning_pct / reasoning_traffic_pct) if reasoning_traffic_pct else 0.0
    reasoning_cap = {
        "current_traffic_pct": round(reasoning_traffic_pct, 1),
        "target_traffic_pct": target_reasoning_pct,
        "daily_cost_savings": round(cost_by_reasoning[True] * excess_factor, 2),
        "daily_wh_savings": round(wh_by_reasoning[True] * excess_factor, 1),
    }

    if verbose:
        print("== M2 Inference Cost Levers ==")
        print(f"requests={len(rows)}  tokens={total_tokens:,}")
        print(f"baseline  : ${base_cost:,.2f}/day   ${base_pm:.3f}/1M-token")
        print(f"optimized : ${opt_cost:,.2f}/day   ${opt_pm:.3f}/1M-token")
        print(f"savings   : {savings_pct:.1f}%  (cascade + caching + batch)")
        print(f"discount stack (batch + 100% cache): {pricing.discount_stack(batch=True, cache_hit_frac=1.0):.3f} of naive")
        print("\nYour Turn: cache economics")
        for tier, c in cache_policy.items():
            print(f"  {tier:5} avg_reads={c['avg_cache_reads']:>5}  break_even={c['break_even_reads']:>4}  worth_it={c['cache_worth_it']}")
        print("\nYour Turn: reasoning budget")
        print(f"  reasoning traffic: {reasoning_requests}/{len(rows)} requests ({reasoning_traffic_pct:.1f}%)")
        print(f"  reasoning cost: ${cost_by_reasoning[True]:.2f}/day ({reasoning_cost_pct:.1f}% of optimized spend)")
        print(f"  reasoning energy: {wh_by_reasoning[True]:,.1f} Wh/day vs {wh_by_reasoning[False]:,.1f} Wh/day non-reasoning")
        print(f"  cap rule: route to reasoning only for eval/high-complexity tasks; cap at {target_reasoning_pct:.0f}% traffic")

    return {
        "baseline_daily": round(base_cost, 2), "optimized_daily": round(opt_cost, 2),
        "baseline_per_m": round(base_pm, 3), "optimized_per_m": round(opt_pm, 3),
        "savings_pct": round(savings_pct, 1), "total_tokens": total_tokens,
        "cache_policy": cache_policy,
        "reasoning": {
            "requests": reasoning_requests,
            "traffic_pct": round(reasoning_traffic_pct, 1),
            "cost_daily": round(cost_by_reasoning[True], 2),
            "cost_pct": round(reasoning_cost_pct, 1),
            "wh_daily": round(wh_by_reasoning[True], 1),
            "non_reasoning_wh_daily": round(wh_by_reasoning[False], 1),
            "cap_policy": reasoning_cap,
        },
    }


if __name__ == "__main__":
    run()
