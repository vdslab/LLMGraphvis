---
name: reading-the-drawing
description: Reading what the current drawing shows (where groups, hubs and components sit, whether colors separate) from numbers instead of an image. Load before describing the picture or answering where something is on it.
triggers: [図から, 図を説明, 図の説明, 何が読み取れ, 読み取れる, どう見える, 見た目を説明, 図のどこ, 図の中で, どこにあ, どこに集ま, どの辺, まとまって, 分かれて, 固まって, 散らば, 偏って, 中心にある, 周辺にある, 外れ値, describe the drawing, describe the picture, what does the graph show, what does the drawing show, where are the, clustered together, separated, spread out, outlier]
related_tools: [visualization_describe, visualization_get_state, visualization_generate, visualization_highlight]
---

## Measure, then speak

Before telling the user what the picture shows, call `visualization_describe`.
It measures the drawing as the canvas draws it, so what you say matches what
they see. Never infer positions from the layout's name or from the algorithm.

- **Where something is**: use the region names (`top-left`, `center`, ...)
  and `placement` (core / middle / periphery). Do not quote coordinates.
- **Whether groups form clusters**: judge from `separation` and each group's
  `cohesion` against its `chance`, not from the group's `spread` alone. A group
  with several `main_regions` is split across the drawing; say where each part is.
- **Whether a metric relates to position**: `numeric_placement`'s
  `center_correlation` says if high values sit toward the center (positive) or
  the edge (negative); near zero means no pattern worth reporting.
- **Hubs, islands, stragglers**: `prominent_nodes`, `components`, `outliers`.
- **Naming nodes**: name only nodes the result lists (`high_values.nodes`,
  `prominent_nodes`, `outliers`), never from what you know of the dataset.

## Choosing the groups

By default the groups are the categories node color shows. To check a grouping
that is not on screen (e.g. a community attribute while color shows something
else), pass it as `group_by`; say that it is not what the colors show.

## Limits to state

The description is of the whole drawing; the user's zoom is not known. If they
are zoomed in, say the description covers everything, not just what is in view.
A position reflects the layout, not the data: nodes far apart are not
necessarily unrelated. Say so when a conclusion would rest on distance alone.
