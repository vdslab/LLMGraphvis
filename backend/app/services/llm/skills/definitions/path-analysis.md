---
name: path-analysis
description: Choose reachability, shortest paths, or source distances and clarify edge-cost semantics.
triggers: [path, route, reachability, distance, shortest, alternative, 経路, 最短, 距離, 到達, 何ステップ, ホップ, パス, ルート, 道筋, 別の経路, 迂回, 共通の隣, 共通点]
related_tools: [node_search, analysis_has_path, analysis_shortest_path, analysis_k_shortest_paths, analysis_single_source_distances, node_common_neighbors, visualization_highlight, visualization_set_viewport, visualization_set_node_labels, network_list_edge_attributes]
---

## Choose the question

- Can A reach B? Use `analysis_has_path`; do not compute centrality or extract a graph.
- Which route is shortest? Use `analysis_shortest_path` with both exact node IDs.
- What other routes exist? Use `analysis_k_shortest_paths` (shortest first).
- How far can we go from A? Use `analysis_single_source_distances`, optionally
  with a cutoff. It lists only the nearest nodes (`limit`) plus a summary of
  all reachable ones; pass `target_node_ids` when specific distances matter.
- What connects A and B directly? Use `node_common_neighbors`.

Resolve labels using `node_search`. Ambiguous matches require the user's choice.
Paths follow outgoing edges (source -> target) when the network is directed;
reverse reachability is not implied unless an explicit return edge exists.
Undirected networks allow traversal in both directions.

## Clarify what distance means

**Default: omit `weight`** and report hops. Unweighted paths minimize hop
count. Pass a weight only when the user says what makes an edge long (distance,
cost, time) and names or confirms the attribute. In path algorithms, an edge weight is
interpreted as a **cost or distance**: larger values make an edge less
desirable (longer). This is the **opposite** of layout or community algorithms,
where weights represent connection strength (larger = closer/stronger).
Never pass a connection-strength attribute as a path weight. If the edge
semantics are ambiguous, ask the user which attribute represents distance or cost.
Missing values in a selected numeric edge attribute default to 1.0; mention this
if it affects interpretation.

Dijkstra requires nonnegative costs. Bellman-Ford accepts negative costs, but a
reachable negative cycle means no finite shortest-path result exists. Explain
that condition instead of retrying the same query or changing weights silently.

## Report the result accurately

Distinguish hops from total cost. A returned path is one optimum, not proof of a
unique route. No path is an answer, not a tool malfunction. Missing nodes in a
distance result may be unreachable or excluded by cutoff; do not report zero.
These tools do not change the view. When the user wants to *see* a route
("show", "display", "見せて", "表示"), draw it with
`visualization_highlight(node_ids=<path>, edges='path', zoom_to=True)` in the
next response, together with `visualization_set_node_labels(visibility='highlighted')`
when the user wants the route's names. `zoom_to` already moves the view; do not
follow it with `visualization_set_viewport`. See `view-navigation`. Do not
extract a subgraph to show a path.
