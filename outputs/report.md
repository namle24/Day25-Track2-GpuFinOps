# NimbusAI — GPU Cost Optimization Report

**Period:** monthly  
**Baseline spend:** $27,133  
**Optimized spend:** $14,626  
**Projected savings:** $12,507  (**46%**)

## Savings by lever

| Lever | Savings (USD) |
|---|---|
| Inference (cascade/cache/batch) | $1,212 |
| Purchasing (spot/reserved) | $10,040 |
| Right-size util-lies | $655 |
| Kill idle GPUs | $600 |

## Technical analysis

- GPU-Util is not efficiency: `gpu-h100-4` shows high busy-clock utilization while MFU is only 19%. This means kernels keep the device active, but memory stalls, launch overhead, or poor arithmetic intensity waste most paid FLOPs.
- Priority 1 is purchasing policy because it saves $10,040/month with no product change; Priority 2 is inference routing/cache/batch because it cuts $/1M-token from $6.488 to $1.126; Priority 3 is right-sizing and idle shutdown for direct waste removal.
- Use chargeback only after tag coverage stays above 80%; below that threshold, missing tags make team-level bills misleading.

## Sustainability

- Energy per query: 0.24 Wh
- Carbon per query: 0.091 gCO2e
- Cheapest+cleanest region: europe-north1
- Best-region electricity cost per query: $0.00002160

## Your Turn extensions

### Cache economics

| Tier | Avg cached reads | Break-even reads | Use cache? |
|---|---:|---:|---|
| small | 237.8 | 0.28 | True |
| large | 62.2 | 0.28 | True |

### Reasoning budget

- Reasoning is 8.4% of requests but 16.5% of optimized inference spend.
- Daily energy: 29,787.7 Wh for reasoning vs 1,887.6 Wh for non-reasoning.
- Routing rule: send only eval/high-complexity tasks to reasoning and cap the route at 5% traffic. Estimated savings at this cap: $0.56/day and 12,004.0 Wh/day.

_Figures are June-2026 as-of snapshots; re-baseline before acting._