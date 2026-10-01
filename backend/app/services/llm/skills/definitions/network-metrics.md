---
name: network-metrics
description: Which structural metric answers which question — the full set of centralities (closeness, eigenvector, clustering, in/out degree), bottlenecks (bridges, articulation points) and components of directed graphs — and whether each saves an attribute or only returns values. Load this when the question needs a metric beyond degree, betweenness, PageRank or communities.
triggers: [closeness, eigenvector, clustering coefficient, in-degree, out-degree, indegree, outdegree, bridge, articulation, cut vertex, bottleneck, strongly connected, weakly connected, 近接中心性, 固有ベクトル, クラスタ係数, 入次数, 出次数, ブリッジ, 切断点, 関節点, ボトルネック, 強連結, 弱連結, 有向, 橋渡し, broker, bridging, 仲介, つなぎ役, 孤立, isolated, 分断, fragment]
related_tools: [analysis_closeness_centrality, analysis_eigenvector_centrality, analysis_clustering_coefficient, analysis_in_degree_centrality, analysis_out_degree_centrality, analysis_degree_centrality, analysis_betweenness_centrality, analysis_pagerank, analysis_bridges, analysis_articulation_points, analysis_connected_components, analysis_weakly_connected_components, analysis_strongly_connected_components, node_get_top_ranked, visualization_highlight]
---

## Match the question to the metric

| The user asks | Tool | Result |
|---|---|---|
| Who reaches everyone quickly? | `analysis_closeness_centrality` | saves `closeness_centrality` |
| Who is connected to other important nodes? | `analysis_eigenvector_centrality` | saves `eigenvector_centrality` |
| How clique-like is each node's neighbourhood? | `analysis_clustering_coefficient` | saves `clustering` |
| Who receives / sends the most links (directed)? | `analysis_in_degree_centrality` / `analysis_out_degree_centrality` | saves `in_degree_centrality` / `out_degree_centrality` |
| Which single link or node would split the network? | `analysis_bridges` / `analysis_articulation_points` | returns values only |
| How does a directed network fall apart? | `analysis_weakly_connected_components` (any chain of links) / `analysis_strongly_connected_components` (mutual reachability) | returns values only |

For hubs, brokers and prestige use `analysis_degree_centrality`,
`analysis_betweenness_centrality` and `analysis_pagerank` (see `analysis-planning`).

## Saved attributes versus returned values

A tool that saves an attribute answers nothing by itself: read the top nodes
with `node_get_top_ranked` using the exact attribute name from the tool's reply,
or map it to colour or size (`visual-encoding`). A tool that returns values
already holds the answer; show the nodes it names with `visualization_highlight`
rather than extracting them.

## Direction and weights

- Undirected-only tools (`analysis_bridges`, `analysis_articulation_points`,
  `analysis_connected_components`, `analysis_clustering_coefficient`) refuse a
  directed network; use the weakly/strongly connected variants there.
- Closeness and betweenness read a weight as a **cost** (larger = farther).
  Leave `weight` unset unless the user said edges are distances; an imported
  strength weight would invert the result.
- Eigenvector centrality and PageRank read a weight as **strength**.

## Report

Name the metric in plain words, what a high value means on this data, and the
top nodes with their values. Say that a metric describes the graph it was
computed on, not a subgraph extracted later.
