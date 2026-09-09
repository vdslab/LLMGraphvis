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
Paths follow outgoing edges when the network is directed; reverse reachability is
not implied. Previously imported data may need re-importing to recover direction
that older versions did not preserve.

## Clarify what distance means

Unweighted paths minimize hop count. An edge weight used here is a cost or distance:
larger values make an edge less desirable. Connection strength is not a cost;
ask which attribute represents distance if the request or data is ambiguous.
Never silently invert or substitute a strength attribute. Missing values in a
selected numeric edge attribute default to one; mention this if it affects interpretation.

Dijkstra requires nonnegative costs. Bellman-Ford accepts negative costs, but a
reachable negative cycle means no finite shortest-path result exists. Explain
that condition instead of retrying the same query or changing weights silently.

## Report the result accurately

Distinguish hops from total cost. A returned path is one optimum, not proof of a
unique route. No path is an answer, not a tool malfunction. Missing nodes in a
distance result may be unreachable or excluded by cutoff; do not report zero.
These tools do not change the view. Extracting or styling a route is a separate
operation, only when it serves the user's request.
