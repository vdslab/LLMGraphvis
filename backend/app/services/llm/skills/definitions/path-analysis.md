---
name: path-analysis
description: Choose reachability, shortest paths, or source distances and clarify edge-cost semantics.
triggers: [path, reachability, distance, shortest, 経路, 最短, 距離, 到達, 何ステップ, ホップ]
related_tools: [node_search, analysis_has_path, analysis_shortest_path, analysis_single_source_distances, network_list_edge_attributes]
---

## Choose the question

- Can A reach B? Use `analysis_has_path`; do not compute centrality or extract a graph.
- Which route is shortest? Use `analysis_shortest_path` with both exact node IDs.
- How far can we go from A? Use `analysis_single_source_distances`, optionally with a cutoff.

Resolve labels using `node_search`. Ambiguous matches require the user's choice.
Paths follow outgoing edges (source -> target) when the network is directed;
reverse reachability is not implied unless an explicit return edge exists.
Undirected networks allow traversal in both directions.

## Clarify what distance means

Unweighted paths minimize hop count. In path algorithms, an edge weight is
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
These tools do not change the view. Extracting or styling a route is a separate
operation, only when it serves the user's request.
