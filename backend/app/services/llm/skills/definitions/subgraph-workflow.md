---
name: subgraph-workflow
description: Extract a network, select the analysis context, lay it out, and render as separate decisions. Load before extracting or switching networks.
triggers: [subgraph, 部分グラフ, サブグラフ, filter, フィルタ, 絞り, 抽出, extract, focus, フォーカス, 注目, zoom, ズーム, only, のみ, だけ, component, 連結成分, ego, 近傍, neighbor, k-core, コア, 戻, back, parent, 親]
related_tools: [subgraph_extract_filter, subgraph_extract_nodes, network_select, subgraph_list, analysis_connected_components, visualization_generate, layout_spring, ask_user, switch_to_parent_network, switch_to_main_network]
---

## Separate selection, extraction, and viewing

Use `subgraph_extract_filter` for attribute conditions. Conditions use
`attribute_name`, with AND across conditions and OR among categories/ranges.
Use `subgraph_extract_nodes` when the user named IDs or analysis returned a small
set of IDs. Do not enumerate thousands of IDs to simulate an attribute filter.
For communities, filter the exact saved community attribute and value.

These tools return `created_network_id` and leave the active network and canvas
unchanged. They create a fresh induced subgraph, copy source attributes, and
exclude derived metrics and coordinates. They do not inherit visual styles.

If the user asked only to create or compare a subset, analysis can use the
returned ID explicitly while staying on the current graph. If the user asked
to view it, use this sequence:

1. Extract with the appropriate atomic tool.
2. `network_select(network_id=created_network_id)` changes subsequent analysis.
3. Calculate a layout on that network.
4. Recompute any metrics needed for encoding; use the returned attribute names.
5. `visualization_generate` draws the result.

Report the resulting scope. Do not imply that centrality computed on the parent
is a property of the subgraph. If a filtering request is ambiguous, ask one
concrete question with `ask_user` and wait; do not extract before the answer.

## Preserve an existing spatial arrangement

For an explicit request to keep parent positions, the legacy
`subgraph_create_from_nodes(..., preserve_layout=True)` remains available.
Unlike the atomic tools, legacy `subgraph_create_*`, `subgraph_ego_network`,
`subgraph_k_core`, `subgraph_community`, and other older extraction tools
**automatically switch and render** through a backend hook. Do not repeat the
switch. When `preserve_layout=False`, they also compute an initial layout.
Use these only when that compound behavior matches the user's request.
Derived metrics are excluded even when positions are retained, so recompute
before interpreting or mapping them.

## Return to an earlier network

Use `subgraph_list` to discover saved children. `network_select` changes only
analysis context; follow it with `visualization_generate` to show the saved view.
`switch_to_parent_network` and `switch_to_main_network` are legacy shortcuts that
also render. Explain the scope change without exposing implementation details.
