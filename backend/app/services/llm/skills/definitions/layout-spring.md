---
name: layout-spring
description: Tuning the spring (Fruchterman-Reingold) layout — spacing, iterations, and the energy method with gravity for graphs in several parts. Load with `layout` when the spring layout is (or will be) used.
triggers: [spring, ばね, バネ, fruchterman, フルクターマン]
related_tools: [layout_spring, layout_suggest_parameters, visualization_generate]
---

## Strategy

| Issue / request | First move | If not enough |
|---|---|---|
| `node_overlap` | `iterations` (fewer often helps on trees and sparse graphs, where long runs pile leaves together) | `k` in either direction; let `layout_suggest_parameters` compare |
| `outliers_compress_core`, separate parts drift off | `method='energy'` with a higher `gravity` | raise `k` |
| `uneven_edge_lengths` | more `iterations` | lower `threshold` |
| "spread it out" / "tighter" | raise / lower `k` | — |
| Keep some nodes where they are | `fixed=[...]` with `init_from_layout` | — |

## Notes

- `gravity` acts only with `method='energy'`; passing it alone changes nothing. Graphs in several parts get the energy method automatically (see the reply's "Auto-tuned" note).
- Because the drawing is rescaled to the canvas, `k` changes spacing *relative to the whole graph*; its effect on overlap is not monotonic.
