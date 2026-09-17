---
name: layout-tuning
description: Choosing a layout algorithm and mapping natural-language requests ("spread them out", "use the weights") onto specific layout parameters. Load this whenever node positions are the subject.
triggers: [layout, レイアウト, 配置, spread, 広げ, 離し, 密, tight, 詰ま, 重な, overlap, 見づら, position, 座標, force, ばね, spring, forceatlas, circular, 円, 円形, kamada, spectral, spiral, tree, 木, 階層, seed, 再現, weight, 重み]
related_tools: [layout_forceatlas2, layout_spring, layout_kamada_kawai, layout_spectral, layout_circular, layout_shell, layout_spiral, layout_random, layout_arf, layout_bipartite, layout_multipartite, layout_planar, layout_bfs, visualization_generate, visualization_get_state, offer_parameter_tuning, apply_parameter_tuning]
---

## Two-Step Execution Invariant

Layout tools compute and store coordinates; they do **not** draw.
1. `layout_<algorithm>(...)` — compute coordinates.
2. `visualization_generate()` — render updated coordinates on screen.

## Algorithm Selection

- **`layout_forceatlas2`**: Default. Emphasizes communities and scales to large graphs.
- **`layout_spring`** (Fruchterman-Reingold): Uniform spacing, less extreme clustering.
- **`layout_kamada_kawai`**: High-quality global layout for small graphs (<300 nodes). O(N²) memory/time; unweighted by default.
- **`layout_arf`**: Force layout with adjustable attraction/repulsion; alternative when ForceAtlas2 overlaps.
- **`layout_circular` / `layout_shell` / `layout_spiral`**: Geometric layouts for ordered/partitioned views (`nlist`).
- **`layout_bipartite` / `layout_multipartite`**: Partition-based layers.
- **`layout_bfs`**: Hierarchical tree levels from a root node.
- **`layout_spectral`**: Fast eigenvector layout; may collapse dense graphs into lines.
- **`layout_planar`**: Crossing-free layout for strictly planar graphs only.

## Parameter Mapping Guide

Parameters auto-tune to graph size by default. Override only when requested:

| User Request | Parameter Change |
|---|---|
| "spread them out" / overlap | ForceAtlas2: raise `scaling_ratio`, lower `gravity`. Spring: raise `k`. |
| "pull it together" / sparse | ForceAtlas2: lower `scaling_ratio`, raise `gravity`. Spring: lower `k`. |
| "big nodes overlap" | ForceAtlas2: `node_size=True` (size-aware repulsion). |
| "converge better" | Raise `max_iter` (ForceAtlas2) or `iterations` (Spring). |
| "use edge weights" | Already applied by default. Do not pass `weight='weight'`. |
| "use <attr> as weight" | Pass `weight='<attr>'` (must be numeric edge attribute). |
| "ignore weights" | Pass `weight='none'`. |
| "reproducible / same result"| Pass explicit integer `seed`. |
| "try different arrangement"| Change `seed`, with `force_recompute=True`. |
| "sharper clusters" | ForceAtlas2: `strong_gravity=True` or `linlog=True`. |
| "refine current shape" | `init_from_layout='<previous_layout_name>'`. |

## Edge Weight Semantics & Invariants

- **Default Weighting**: `forceatlas2`, `spring`, and `spectral` automatically use imported positive edge weights as connection strength.
- **Kamada-Kawai**: Interprets weight as target *distance* (higher = farther). Never weighted by default.
- **Coordinates Normalized**: Canvas normalizes coordinates to [-1000, 1000]. Parameters `scale` and `center` are visually inert — never offer them as zoom or pan.
- **Caching**: Layouts cache by topology hash and parameters. Use `force_recompute=True` only when explicitly retrying the exact same parameters.

## Procedures

### Adjusting Current Layout
1. Call `visualization_get_state` to identify the active layout algorithm if unknown.
2. Re-call that layout tool with the modified parameter.
3. Call `visualization_generate()`.
4. Report the adjusted parameter and value clearly.
