---
name: analysis-planning
description: How to propose analysis and visualization goals from the imported data meaning, descriptions, and existing attributes before considering computed metrics. Load this for "analyze this network" style requests, or before computing a metric or community structure.
triggers: [visualization, possibilities, 分布, distribution, 比較, compare, 違い, 偏り, つながり方, 可視化, 何ができる, analyze, analyse, 特徴, 傾向, 構造, structure, important, influential, 中心, community, コミュニティ, クラスタ, cluster, group, centrality, 中心性, metric, 指標, attribute, 属性, 影響力, influence, 人気, popular, まとめ役, リーダー, leader, key player, 重要人物, 何がわか, 何が分か, 全体像, overview, どこから, where to start, 主要]
related_tools: [network_list_node_attributes, visualization_set_node_color, visualization_set_node_size, visualization_set_node_labels, network_list_edge_attributes, analysis_louvain_communities, analysis_greedy_modularity_communities, analysis_label_propagation_communities, ask_user, analysis_degree_centrality, analysis_pagerank, analysis_betweenness_centrality, node_get_top_ranked, analysis_core_number, analysis_triangles, analysis_transitivity, analysis_edge_betweenness, analysis_modularity, analysis_attribute_distribution, analysis_group_connectivity, node_compare, node_get_details, node_filter, offer_parameter_tuning, analysis_connected_components]
---

## Data-Grounded Analysis Workflow

This choice workflow applies to an **open-ended** request. If the user already names a question, attribute, metric, or method, carry it out directly and report its interpretation. Do not insert a goal menu before a specific analysis.

For open-ended analysis requests ("analyze this network", "what can you tell me?"):

1. **Inspect Context First**:
   - Read `[Current Network Context]` for imported attributes, statistics, and descriptions.
   - Unmarked attributes came with the file; attributes marked `[derived]` were computed here. Never present computed metrics as imported facts.
   - Do not guess or invent metadata; state uncertainties plainly.
2. **Prioritize Existing Attributes**:
   - If the user asks about "groups" or "categories", check attributes whose measurement is `categorical` (`club`, `department`, `genre`) before running community detection. A `discrete` attribute may also be a group code; its name and description tell.
   - `identifier` attributes name nodes (labels, search); `text` attributes are prose to read and quote. Neither answers a question as an encoding.
   - Compute new structural metrics/communities only when no recorded attribute answers the question, or when structural topology is explicitly requested.
3. **Formulate Concrete Goals**:
   - Propose 2–3 specific questions the data can answer, describing what each option will reveal on screen.
   - Never classify goals with technical labels like "positional", "structural", or "位置ベース".
   - Propose a whole view (e.g. recorded group on color × structural metric on size; see `visual-encoding`).
4. **Formulate Choice via `ask_user`**:
   - Provide explanation text and the `ask_user` call in the **same response**. Never send a bare form without explanatory text.
   - Use `fields=[{"id": "analysis_goal", "label": "Analysis goal", "kind": "select", "options": [...]}]`.
   - Keep `allow_other=true` (free-text is auto-provided by UI). Do not add a separate text input field.
   - Match the user's conversation language.

## Plain Questions Are Specific Requests

A question without metric names ("who is most influential?", "who connects the groups?", "is anyone isolated?") is a specific request, not an open-ended one. Pick the matching metric, compute it, and answer on the canvas in the same turn:

| The user asks | Metric |
|---|---|
| Who is popular / has the most ties | `analysis_degree_centrality` |
| Who is influential / connected to important others | `analysis_pagerank` |
| Who bridges or mediates between groups | `analysis_betweenness_centrality` |
| Which groups form | a recorded categorical attribute first, else `analysis_louvain_communities` |
| Who is isolated or cut off | `analysis_connected_components` (see `network-metrics`) |

Then show the answer: size by the saved metric (`visualization_set_node_size`), label the top nodes (`visualization_set_node_labels(visibility='top_n', rank_by=<metric>)`), and say in one sentence what the metric measures on this data. Add colour only for a second part of the question.

When the user is new to network analysis, phrase options as questions about the data rather than algorithm names. When the user asks for a specific method, keep its exact name and parameters in the report so the result is reproducible. In either case, distinguish a fact computed from links from an attribute supplied with the GraphML file.

## Metric and Topology Rules

- **Attribute Name Verification**: Read exact, case-sensitive names from `[Current Network Context]`. Call `network_list_node_attributes` only if the list was truncated or dynamically modified.
- **Read Saved Metric Names**: Persisting tools write attributes under specific names (e.g. `louvain_community`, `pagerank`). Always read the exact name from the tool's return message for styling.
- **Topology Dependence**: Centrality and community scores belong only to the graph on which they were computed. Subgraph extraction excludes derived metrics; recompute them on subgraphs when needed.

## Algorithm Selection & Controls

- **Community Detection**:
  - `analysis_louvain_communities`: Default. Accepts `resolution`, `seed`, `threshold`, `max_level`, `weight`.
  - `analysis_greedy_modularity_communities`: Use `best_n` or `cutoff` to enforce cluster count.
  - `analysis_label_propagation_communities`: Semi-synchronous; no weights or seeds.
- **Centrality**:
  - `analysis_betweenness_centrality`: Measures bridging roles. Use `k` approximation for large networks.
  - `analysis_degree_centrality` / `analysis_pagerank`: Measures local hub activity / global prestige.
  - Closeness, eigenvector, clustering, in/out degree, bridges, articulation points and directed components: load `network-metrics`.
- **Read-Only Structural Metrics** (return values without saving node attributes):
  - `analysis_core_number`: Cohesive k-core depth.
  - `analysis_triangles` / `analysis_transitivity`: Local and global clustering.
  - `analysis_edge_betweenness`: Shortest-path traffic on edges (interprets weight as distance).
  - `analysis_modularity`: Partition quality evaluation.

## Ask Precise Questions, Read Small Answers

Tool results are re-sent on every later request, so prefer the tool whose
answer is already the summary the user needs:

- "How is X spread / which group has the most X" → `analysis_attribute_distribution`
  (with `group_by` for per-group statistics), not a list of nodes.
- "How do the groups connect / are they separated" → `analysis_group_connectivity`.
- Describing or contrasting several nodes → one `node_compare`, not repeated
  `node_get_details`.
- Per-node results (`analysis_core_number`, `analysis_triangles`, distances)
  list only the top entries plus a whole-network `summary`; raise `limit` only
  when more individual values are needed.
