"""Report assembly — the lab's deliverable: baseline vs optimized + savings chart."""
from __future__ import annotations


def build_report(baseline_usd: float, optimized_usd: float, levers: dict,
                 sustainability: dict | None = None, period: str = "monthly",
                 analysis: dict | None = None, extensions: dict | None = None) -> str:
    """Return a markdown cost-optimization report."""
    savings = baseline_usd - optimized_usd
    pct = (savings / baseline_usd * 100.0) if baseline_usd > 0 else 0.0
    lines = [
        "# NimbusAI — GPU Cost Optimization Report",
        "",
        f"**Period:** {period}  ",
        f"**Baseline spend:** ${baseline_usd:,.0f}  ",
        f"**Optimized spend:** ${optimized_usd:,.0f}  ",
        f"**Projected savings:** ${savings:,.0f}  (**{pct:.0f}%**)",
        "",
        "## Savings by lever",
        "",
        "| Lever | Savings (USD) |",
        "|---|---|",
    ]
    for name, amount in levers.items():
        lines.append(f"| {name} | ${amount:,.0f} |")
    if analysis:
        lines += [
            "",
            "## Technical analysis",
            "",
            f"- GPU-Util is not efficiency: `{analysis.get('util_lie_gpu', 'n/a')}` shows high busy-clock utilization while MFU is only {analysis.get('util_lie_mfu', 0):.0%}. This means kernels keep the device active, but memory stalls, launch overhead, or poor arithmetic intensity waste most paid FLOPs.",
            f"- Priority 1 is purchasing policy because it saves ${analysis.get('purchasing_savings', 0):,.0f}/month with no product change; Priority 2 is inference routing/cache/batch because it cuts $/1M-token from ${analysis.get('baseline_per_m', 0):.3f} to ${analysis.get('optimized_per_m', 0):.3f}; Priority 3 is right-sizing and idle shutdown for direct waste removal.",
            "- Use chargeback only after tag coverage stays above 80%; below that threshold, missing tags make team-level bills misleading.",
        ]
    if sustainability:
        lines += [
            "",
            "## Sustainability",
            "",
            f"- Energy per query: {sustainability.get('wh_per_query', 0):.2f} Wh",
            f"- Carbon per query: {sustainability.get('carbon_g', 0):.3f} gCO2e",
            f"- Cheapest+cleanest region: {sustainability.get('best_region', 'n/a')}",
        ]
        if "best_region_energy_cost" in sustainability:
            lines.append(f"- Best-region electricity cost per query: ${sustainability.get('best_region_energy_cost', 0):.8f}")
    if extensions:
        lines += ["", "## Your Turn extensions", ""]
        cache = extensions.get("cache")
        if cache:
            lines += [
                "### Cache economics",
                "",
                "| Tier | Avg cached reads | Break-even reads | Use cache? |",
                "|---|---:|---:|---|",
            ]
            for tier, c in cache.items():
                lines.append(f"| {tier} | {c['avg_cache_reads']} | {c['break_even_reads']} | {c['cache_worth_it']} |")
        reasoning = extensions.get("reasoning")
        if reasoning:
            cap = reasoning.get("cap_policy", {})
            lines += [
                "",
                "### Reasoning budget",
                "",
                f"- Reasoning is {reasoning.get('traffic_pct', 0):.1f}% of requests but {reasoning.get('cost_pct', 0):.1f}% of optimized inference spend.",
                f"- Daily energy: {reasoning.get('wh_daily', 0):,.1f} Wh for reasoning vs {reasoning.get('non_reasoning_wh_daily', 0):,.1f} Wh for non-reasoning.",
                f"- Routing rule: send only eval/high-complexity tasks to reasoning and cap the route at {cap.get('target_traffic_pct', 5):.0f}% traffic. Estimated savings at this cap: ${cap.get('daily_cost_savings', 0):,.2f}/day and {cap.get('daily_wh_savings', 0):,.1f} Wh/day.",
            ]
    lines += ["", "_Figures are June-2026 as-of snapshots; re-baseline before acting._"]
    return "\n".join(lines)


def savings_waterfall(levers: dict, path: str) -> str:
    """Write a simple savings bar chart PNG. Returns the path."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return _savings_waterfall_pillow(levers, path)
    names = list(levers.keys())
    vals = [levers[n] for n in names]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(names, vals, color="#2e548a")
    ax.set_ylabel("Savings (USD / month)")
    ax.set_title("GPU cost savings by FinOps lever")
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path


def _savings_waterfall_pillow(levers: dict, path: str) -> str:
    """Fallback chart for minimal environments without matplotlib."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return ""

    width, height = 1100, 620
    margin_l, margin_r, margin_t, margin_b = 90, 50, 70, 170
    plot_w = width - margin_l - margin_r
    plot_h = height - margin_t - margin_b
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    vals = list(levers.values())
    names = list(levers.keys())
    max_val = max(vals) if vals else 1
    draw.text((margin_l, 25), "GPU cost savings by FinOps lever", fill="#1f2937", font=font)
    draw.line((margin_l, margin_t, margin_l, margin_t + plot_h), fill="#374151", width=2)
    draw.line((margin_l, margin_t + plot_h, margin_l + plot_w, margin_t + plot_h), fill="#374151", width=2)
    for i in range(5):
        y = margin_t + plot_h - int(plot_h * i / 4)
        val = max_val * i / 4
        draw.line((margin_l - 5, y, margin_l + plot_w, y), fill="#e5e7eb", width=1)
        draw.text((10, y - 7), f"${val:,.0f}", fill="#374151", font=font)

    bar_slot = plot_w / max(len(vals), 1)
    bar_w = int(bar_slot * 0.55)
    colors = ["#2563eb", "#059669", "#d97706", "#7c3aed"]
    for i, (name, val) in enumerate(zip(names, vals)):
        x0 = int(margin_l + i * bar_slot + (bar_slot - bar_w) / 2)
        x1 = x0 + bar_w
        bar_h = int((val / max_val) * (plot_h - 8)) if max_val else 0
        y0 = margin_t + plot_h - bar_h
        y1 = margin_t + plot_h
        draw.rectangle((x0, y0, x1, y1), fill=colors[i % len(colors)])
        draw.text((x0, y0 - 18), f"${val:,.0f}", fill="#111827", font=font)
        words = name.replace("(", "\n(").split("\n")
        for j, part in enumerate(words):
            draw.text((x0, y1 + 14 + j * 14), part[:28], fill="#111827", font=font)

    img.save(path)
    return path
