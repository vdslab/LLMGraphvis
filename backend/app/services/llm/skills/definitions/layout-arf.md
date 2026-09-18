---
name: layout-arf
description: Tuning the ARF (attractive-repulsive force) layout — repulsion scale and spring strength. Load with `layout` when ARF is used, typically as an alternative when ForceAtlas2 overlaps.
triggers: [arf, attractive, repulsive, 引力, 斥力]
related_tools: [layout_arf, layout_suggest_parameters, visualization_generate]
---

## Strategy

| Issue / request | Move |
|---|---|
| `node_overlap`, `clumped`, "spread it out" | raise `scaling` |
| `outliers_compress_core`, "pull it together" | raise `a` (stronger springs relative to repulsion) |
| Not settled / jittery | lower `etol`, or a smaller `dt` (slower) |
| Refine the current shape | `init_from_layout='arf'` |

## Notes

- ARF has no weight parameter; edge weights cannot drive it. Use ForceAtlas2 or spring when weights matter.
- Use ARF when the user wants a force layout but ForceAtlas2 keeps overlapping after tuning.
