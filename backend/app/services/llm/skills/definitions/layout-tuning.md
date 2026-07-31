---
name: layout-tuning
description: Choosing a layout algorithm and mapping natural-language requests ("spread them out", "use the weights") onto specific layout parameters. Load this whenever node positions are the subject.
triggers: [layout, レイアウト, 配置, spread, 広げ, 離し, 密, tight, 詰ま, 重な, overlap, 見づら, position, 座標, force, ばね, spring, forceatlas, circular, 円, 円形, kamada, spectral, spiral, tree, 木, 階層, seed, 再現, weight, 重み]
related_tools: [layout_forceatlas2, layout_spring, layout_kamada_kawai, layout_spectral, layout_circular, layout_shell, layout_spiral, layout_random, layout_arf, layout_bipartite, layout_multipartite, layout_planar, layout_bfs, visualization_generate]
---

## Two steps, always

Layout tools compute coordinates and store them; they do not redraw. Nothing
changes on screen until you render:

1. `layout_<algorithm>(...)` — computes and saves positions.
2. `visualization_generate()` — renders with the newly computed layout.

## Choosing an algorithm

- **`layout_forceatlas2`** — the default. Reveals community structure well and
  scales to large graphs. Use it unless there is a reason not to.
- **`layout_spring`** (Fruchterman–Reingold) — the other general-purpose
  force-directed option; tends to produce more even spacing and less pronounced
  clustering than ForceAtlas2.
- **`layout_kamada_kawai`** — excellent global structure on small graphs, but
  builds a dense N×N distance matrix, so it is O(N²) in both time and memory and
  is refused above a node threshold. Under a few hundred nodes it is often the
  most readable choice.
- **`layout_arf`** — force-directed with attractive/repulsive tuning; a good
  second attempt when ForceAtlas2 leaves too much overlap.
- **`layout_circular` / `layout_shell` / `layout_spiral`** — arrange nodes
  geometrically rather than by structure. Useful when the user wants every node
  visible and evenly spaced, or when shells encode a grouping (`nlist`).
- **`layout_bipartite` / `layout_multipartite`** — when nodes divide into sides
  or layers by an attribute, and that division is the point.
- **`layout_planar`** — only for planar graphs; produces a crossing-free drawing.
  It fails on non-planar input, which is most real graphs.
- **`layout_bfs`** — hierarchical layers by BFS distance from a root. Use for
  trees or when "distance from X" is the question.
- **`layout_spectral`** — positions from the graph Laplacian's eigenvectors.
  Fast and deterministic, but often collapses dense graphs into a line.
- **`layout_random`** — only as a baseline, or as a starting point to re-run a
  force layout from.

## Mapping requests to parameters

The live tool schema is authoritative for names, defaults, and ranges — read it
rather than trusting the values below. Parameters are auto-tuned to graph size by
default, so only override what the user actually asked about.

| The user says | Change |
|---|---|
| "spread them out", "広げて", nodes overlap | ForceAtlas2: raise `scaling_ratio`, lower `gravity`. Spring: raise `k`. |
| "pull it together", "詰めて", too sparse | The reverse: lower `scaling_ratio`, raise `gravity`, lower `k`. |
| "the big nodes overlap" | ForceAtlas2 `node_size` — enables size-aware repulsion so large nodes push each other apart. |
| "make it cleaner / converge better" | Raise `max_iter` (ForceAtlas2) or `iterations` (spring). Costs time roughly linearly. |
| "use the edge weights" | Pass `weight='weight'` (or the actual edge attribute name). **Layouts ignore edge weights unless you pass this** — the graph is built unweighted otherwise. |
| "same result every time", "再現性" | Pass an explicit `seed`. Force layouts start from random positions, so without a fixed seed successive runs differ. |
| "try a different arrangement" | Change `seed`, with `force_recompute=True`. |
| "emphasise the clusters more" | ForceAtlas2 `strong_gravity=True`, or `linlog=True` for a log attraction model that separates clusters more sharply. |
| "keep the current shape but refine it" | `init_from_layout='<previous layout name>'` — warm-starts from stored coordinates instead of from random. |
| "start the circle from the top" | `layout_shell`: `rotate`. |
| "tighter/looser spiral" | `layout_spiral`: `resolution`; `equidistant=True` for even arc spacing. |

`scale` and `center` are accepted but have **no visible effect**: the renderer
normalizes all coordinates to a fixed [-1000, 1000] extent before drawing. Do not
offer them as a way to zoom or reposition, and do not claim they worked.

## Caching and force_recompute

Layout results are cached against the graph's structure hash **and** the exact
parameters used. Re-calling with identical parameters on an unchanged graph
returns instantly from cache; there is no reason to avoid a call for efficiency.

The cache is keyed on parameters, so a genuine parameter change is a cache miss
and recomputes on its own. Pass `force_recompute=True` only when the user
explicitly wants the same computation redone — "recompute", "try again",
"refresh" — or when a run produced a degenerate result you want to retry.

## Typical procedure: "visualize this network"

1. `layout_forceatlas2()`
2. `visualization_generate()`
3. Ask how they would like nodes encoded — by degree, by community, by an
   existing attribute — rather than assigning colours yourself
   (see `visual-encoding`).

## Typical procedure: "spread the nodes out more"

1. Read the current layout from `visualization_get_state` if you do not already
   know which algorithm is active. Tuning the wrong algorithm's parameters does
   nothing visible.
2. Re-call that layout tool with the adjusted parameter.
3. `visualization_generate()`.
4. Report which parameter you changed and to what, so the user can ask for
   "more" or "less" from a known starting point.
