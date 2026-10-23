---
name: layout-spring
description: Tuning the spring (Fruchterman-Reingold) layout — spacing, iterations, and how graphs in several parts are packed part by part. Load with `layout` when the spring layout is (or will be) used.
triggers: [spring, ばね, バネ, fruchterman, フルクターマン]
related_tools: [layout_spring, layout_suggest_parameters, visualization_generate]
---

## Strategy

| Issue / request | First move | If not enough |
|---|---|---|
| `node_overlap` | `iterations` (fewer often helps on trees and sparse graphs, where long runs pile leaves together) | `k` in either direction; let `layout_suggest_parameters` compare |
| `outliers_compress_core`, separate parts drift off | check that `pack_components` is on (the default for graphs in several parts) | with it off: `method='energy'` with a higher `gravity` |
| Wants the parts mixed into one picture, not side by side | `pack_components=False` | add `method='energy'` with `gravity` to keep the parts close |
| `uneven_edge_lengths` | more `iterations` | lower `threshold` |
| "spread it out" / "tighter" | raise / lower `k` | — |
| Keep some nodes where they are | `fixed=[...]` with `init_from_layout` | — |

## Notes

- `gravity` acts only with `method='energy'`; passing it alone changes nothing. With `pack_components` on, the packing places the parts and `gravity` has nothing to hold together.
- Graphs in several parts are packed automatically: the largest part in the middle, the others around it (see the reply's "Auto-tuned" note). Starting positions (`init_from_layout`, `pos`) turn the packing off for that run.
- When packed, a large part may stop before `iterations` if its earlier state is more readable; the reply says when this applies. Raising `iterations` does not force the longer run.
- Because the drawing is rescaled to the canvas, `k` changes spacing *relative to the whole graph*; its effect on overlap is not monotonic.
