---
name: layout-partitioned
description: Layouts that place nodes by a partition or a root — bipartite, multipartite, shell and bfs — and how to pick the attribute or root they need. Load with `layout` when the user wants sides, layers, rings or a hierarchy.
triggers: [bipartite, 二部, multipartite, 多部, layer, レイヤー, 層, shell, 同心円, ring, bfs, 幅優先, hierarchy, ヒエラルキー, 階層, root, 根, ルート, 左右, 上下]
related_tools: [layout_bipartite, layout_multipartite, layout_shell, layout_bfs, layout_profile, visualization_generate]
---

## Picking the Input

These layouts need something from the data; decide it before calling.

| Layout | Needs | How to choose |
|---|---|---|
| `layout_bipartite` | `partition_attribute` (two values), or `partition_value` to pick one side | A node attribute that splits the graph in two; `layout_profile` says whether the graph is bipartite at all |
| `layout_multipartite` | `subset_attribute` | A node attribute every node has, one layer per value (a community result such as `louvain_community` works) |
| `layout_shell` | `nlist` (lists of node ids, innermost first) | Rings by importance or group; build them from a computed attribute |
| `layout_bfs` | `start` (root node id) | The node the user names, or the most central node; `layout_profile` says whether the graph is a tree |

## Notes

- `align` switches between horizontal and vertical arrangement; `aspect_ratio` shapes the bipartite drawing.
- If the attribute is missing or does not split cleanly, the tool's error says why; compute or pick another attribute rather than retrying.
- These layouts have no readability knobs; `layout_suggest_parameters` only reports their metrics.
