---
name: layout-forceatlas2
description: Tuning ForceAtlas2 — which of its parameters to move for overlap, far-flung parts, clumping or community emphasis, and in what order. Load with `layout` when ForceAtlas2 is (or will be) the layout.
triggers: [forceatlas2, forceatlas, force atlas, fa2, フォースアトラス, 力学モデル, 力指向, force-directed]
related_tools: [layout_forceatlas2, layout_suggest_parameters, visualization_generate]
---

## Strategy

ForceAtlas2 balances repulsion between all nodes (`scaling_ratio`), attraction along edges (weighted by strength), and a pull to the centre (`gravity`). Move one force at a time and re-read `layout_quality`.

| Issue / request | First move | If not enough |
|---|---|---|
| `node_overlap` | `scaling_ratio` (the right direction depends on the graph; `layout_suggest_parameters` tries both) | lower `max_iter`: long runs keep contracting dense regions |
| Large (size-encoded) nodes overlap | `size_aware=True` | raise `scaling_ratio` |
| `outliers_compress_core`, separate parts drift off | raise `gravity` | `strong_gravity=True` |
| `clumped`, "spread it out" | lower `gravity`, or raise `scaling_ratio` | — |
| "pull it together" | raise `gravity` | `strong_gravity=True` |
| "sharper communities" | `linlog=True` (tends to add overlap in dense graphs; pair with `size_aware=True`) | — |
| Hubs swallow their neighbours | `distributed_action=True` (often adds overlap elsewhere; check `layout_quality`) | — |
| "Keep the current shape, just refine" | `init_from_layout='forceatlas2'` with the changed parameter | — |

## Notes

- `gravity` is raised automatically for graphs in several parts; the reply's "Auto-tuned" note says by how much. Lowering it again brings the outliers back.
- `max_iter` sets the runtime. On large graphs prefer the search's candidates over extra manual trials.
- `size_aware=True` uses the node sizes as currently drawn; after changing node sizes, re-run the layout if overlap matters.
