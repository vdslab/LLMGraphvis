---
name: layout
description: Placing nodes — choosing a layout algorithm, reading how readable the drawn layout is (`layout_quality`), and improving it. Load this whenever node positions are the subject, then load the skill for the algorithm in use.
triggers: [layout, レイアウト, 配置, spread, 広げ, 離し, 密, tight, 詰ま, 重な, overlap, 見づら, 見にく, 読みにく, ごちゃ, clutter, 綺麗, きれい, 整え, position, 座標, force, ばね, spring, forceatlas, circular, 円, 円形, kamada, spectral, spiral, tree, 木, 階層, seed, 再現, weight, 重み, quality, 品質]
related_tools: [layout_profile, layout_suggest_parameters, visualization_generate, visualization_get_state, layout_forceatlas2, layout_spring, layout_arf, layout_kamada_kawai, layout_spectral, layout_circular, layout_shell, layout_spiral, layout_random, layout_bipartite, layout_multipartite, layout_planar, layout_bfs, offer_parameter_tuning, apply_parameter_tuning]
---

## Two-Step Invariant

Layout tools compute and store coordinates; they do **not** draw.
1. `layout_<algorithm>(...)` computes coordinates.
2. `visualization_generate()` draws them, and returns `layout_quality`.

## Where the Numbers Come From

Never state a default, a range or a threshold from memory. Read them from tool output:
- The layout tool's reply gives the effective parameters and, under "Auto-tuned", why a default was moved for this graph (e.g. more gravity because the graph is in several parts). Relay that reason when it matters to the user.
- `layout_suggest_parameters` returns `knobs`: each tunable parameter's recommended range and which issue it fixes. Use these ranges for a tuning panel.

## Choosing an Algorithm

When the user has not named one, call `layout_profile` and take the first `recommended` layout that serves the user's goal. Do not use a layout listed as `unsuitable` without saying why it may fail. The profile's reasons are phrased to be relayed.

## Reading `layout_quality`

Every `visualization_generate` reports how the drawing reads, without an image:
- `issues` names what a viewer would notice: `node_overlap`, `outliers_compress_core` (a few far-away nodes squeeze everything else together), `clumped`, `uneven_edge_lengths`, `distorted_aspect`.
- `score` compares layouts **of the same network** only (lower is better). Crossings count toward it but are never an issue on their own: dense graphs cross a lot under any layout.

Tell the user about an issue in plain words ("many nodes overlap"), not as metric names, and only when it affects what they are trying to see.

## Improving a Layout

1. Know the algorithm in use (`visualization_get_state` if unknown) and load its skill: `layout-forceatlas2`, `layout-spring`, `layout-arf`, `layout-kamada-kawai`, or `layout-partitioned` (bipartite, multipartite, shell, bfs). Other algorithms have no parameters that change readability.
2. **A vague complaint** ("hard to read", "cluttered", 見づらい, 重なってる): call `layout_suggest_parameters`. Apply the best candidate by calling `layout_<algorithm>` with its `arguments` exactly, then `visualization_generate`.
3. **A specific request** ("spread it out", "pull the stragglers in"): change the parameter the algorithm skill names for it, re-run, re-draw.
4. Report what changed as parameter before → after, plus what visibly improved or got worse (use `tradeoff` / `metric_deltas`, in words).
5. One search per request. If no candidate improves the score, say so and offer another algorithm from `layout_profile` instead of searching again.
6. The search runs the layout several times, so it is slow on large graphs; `stopped_early` means fewer candidates were tried. Say so rather than retrying.

## Edge Weights

- Layouts that read a weight as **connection strength** (forceatlas2, spring, spectral) use the imported edge weights automatically when they vary. Only the ratios between weights matter; the reply says they were normalized.
- `layout_kamada_kawai` reads a weight as **distance**, so it is never weighted automatically.
- `weight='<attribute>'` uses another numeric edge attribute; `weight='none'` ignores weights.

## Invariants

- Coordinates are renormalized to a fixed canvas, so `scale` and `center` are visually inert. Never offer them as zoom or pan.
- Force layouts are reproducible by default (fixed `seed`). A different `seed` gives a different arrangement of the same graph; `force_recompute=True` is only for redoing identical parameters.
