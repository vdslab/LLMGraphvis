---
name: analysis-planning
description: How to propose analysis and visualization goals from the imported data meaning, descriptions, and existing attributes before considering computed metrics. Load this for "analyze this network" style requests, or before computing a metric or community structure.
triggers: [visualization, possibilities, 可視化, 何ができる, どんな, analyze, analyse, 分析, 特徴, 傾向, 構造, structure, important, 重要, influential, 中心, community, コミュニティ, クラスタ, cluster, group, グループ, centrality, 中心性, metric, 指標, attribute, 属性]
related_tools: [network_list_node_attributes, network_list_edge_attributes, analysis_louvain_communities, analysis_greedy_modularity_communities, analysis_label_propagation_communities, ask_user, analysis_degree_centrality, analysis_pagerank, analysis_betweenness_centrality, node_get_top_ranked, analysis_core_number, analysis_triangles, analysis_transitivity, analysis_edge_betweenness, analysis_modularity]
---

## Data-Grounded Analysis Workflow

For open-ended analysis requests ("analyze this network", "what can you tell me?"):

1. **Inspect Context First**:
   - Read `[Current Network Context]` for imported attributes, statistics, and descriptions.
   - Unmarked attributes came with the file; attributes marked `[derived]` were computed here. Never present computed metrics as imported facts.
   - Do not guess or invent metadata; state uncertainties plainly.
2. **Prioritize Existing Attributes**:
   - If the user asks about "groups" or "categories", check existing categorical attributes (`club`, `department`, `genre`) before running community detection.
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

## Metric and Topology Rules

- **Attribute Name Verification**: Read exact, case-sensitive names from `[Current Network Context]`. Call `network_list_node_attributes` only if the list was truncated or dynamically modified.
- **Read Saved Metric Names**: Persisting tools write attributes under specific names (e.g. `louvain_community`, `pagerank`). Always read the exact name from the tool's return message for styling.
- **Topology Dependence**: Centrality and community scores belong only to the graph on which they were computed. Subgraph extraction excludes derived metrics; recompute them on subgraphs when needed.

## Algorithm Selection & Controls

- **Community Detection**:
  - `analysis_louvain_communities`: Default. Accepts `resolution`, `seed`, `gain_threshold`.
  - `analysis_greedy_modularity_communities`: Use `best_n` or `cutoff` to enforce cluster count.
  - `analysis_label_propagation_communities`: Semi-synchronous; no weights or seeds.
- **Centrality**:
  - `analysis_betweenness_centrality`: Measures bridging roles. Use `k` approximation for large networks.
  - `analysis_degree_centrality` / `analysis_pagerank`: Measures local hub activity / global prestige.
- **Read-Only Structural Metrics** (return values without saving node attributes):
  - `analysis_core_number`: Cohesive k-core depth.
  - `analysis_triangles` / `analysis_transitivity`: Local and global clustering.
  - `analysis_edge_betweenness`: Shortest-path traffic on edges (interprets weight as distance).
  - `analysis_modularity`: Partition quality evaluation.
