---
name: layout-kamada-kawai
description: Using Kamada-Kawai correctly — when it fits, distance-type weights, and warm-starting. Load with `layout` when Kamada-Kawai is considered.
triggers: [kamada, kawai, カマダ, 河合, 距離を保, graph distance, 最短距離]
related_tools: [layout_kamada_kawai, layout_profile, layout_forceatlas2, visualization_generate]
---

## When It Fits

Kamada-Kawai places nodes so drawn distances match shortest-path distances. Check `layout_profile` first: it is recommended only for small, connected graphs and listed as unsuitable otherwise (its cost grows with the square of the node count, and separate parts have no distance between them).

## Procedure

1. Warm-start for speed and to avoid a poor local optimum: run `layout_forceatlas2`, then `layout_kamada_kawai(init_from_layout='forceatlas2')`.
2. Weights are **distances** here. Pass `weight` only for an attribute that means distance or cost; never pass a strength-type weight (it would push strongly connected nodes apart). It is never applied automatically.
3. `dist` (explicit pairwise distances) is almost never needed.

## Notes

- It has no parameters that trade overlap against spread, so `layout_suggest_parameters` only reports its metrics. If it reads badly, switch algorithm rather than tuning.
