---
name: subgraph-workflow
description: Choosing the right extraction tool, deciding whether to keep the parent layout, and what happens to the visual encoding in the new view. Load this before creating or switching to any subgraph.
triggers: [subgraph, 部分グラフ, サブグラフ, filter, フィルタ, 絞り, 抽出, extract, focus, フォーカス, 注目, zoom, ズーム, only, のみ, だけ, component, 連結成分, ego, 近傍, neighbor, k-core, コア, 戻, back, parent, 親]
related_tools: [subgraph_create_by_filter, subgraph_create_from_nodes, subgraph_ego_network, subgraph_k_core, subgraph_community, subgraph_largest_component, subgraph_high_degree_nodes, subgraph_list, visualization_switch_network, switch_to_parent_network, switch_to_main_network]
---

## Pick the tool that matches the selection criterion

Match the user's criterion to a tool rather than reaching for a generic one:

- **By attribute condition** — `subgraph_create_by_filter`, taking a list of
  `{"attribute", "categories", "ranges"}` conditions combined with AND.
  "French citizens", "films from 1990–2000", "nodes with degree above 10".
- **By explicit ID list** — `subgraph_create_from_nodes`. Only when the user
  named specific nodes, or you already hold a small set of IDs from a search.
  **Do not** enumerate IDs to emulate a filter: a several-thousand-ID list
  floods the context window, and the filter runs server-side for free.
- **Around one node** — `subgraph_ego_network` with a `radius`. "Who is
  connected to X?", "X's neighbourhood two hops out".
- **Dense core** — `subgraph_k_core`. Strips peripheral nodes to expose the
  densely connected middle.
- **One detected community** — `subgraph_community`, given the community
  attribute and the id.
- **Cleanup** — `subgraph_largest_component`, to drop isolated nodes and small
  fragments from a noisy graph.
- **Above a degree threshold** — `subgraph_high_degree_nodes`.

Creating a subgraph does not necessarily change what is on screen. Call
`visualization_switch_network(network_id=NEW_ID)` to make it the active view.

## preserve_layout decides what the user sees

This is the most consequential parameter, and it maps onto two genuinely
different intents:

- **`preserve_layout=True`** — "cut out". Nodes keep the coordinates they had in
  the parent, so the selection appears in the same place and at the same relative
  positions it occupied in the whole graph. Use this for **focus / zoom in**,
  when the user wants to look closely at part of a structure they already have a
  mental map of.
- **`preserve_layout=False`** — "fresh". The subgraph is laid out on its own, so
  its internal structure spreads out and becomes readable. Use this when the
  subgraph is now the object of study and its relationship to the parent's
  geometry no longer matters.

Getting this backwards is disorienting: a fresh layout on a "zoom in" request
looks like a completely different graph, and a preserved layout on an
"analyse this cluster" request leaves everything crammed into one corner.

## Visual encoding in the new view

Subgraphs inherit the parent's visual configuration. Usually that is what you
want — consistency across views lets the user carry meaning from one to the next.

Two cases need action:

- **Single-value filter collapses a mapping.** If you filtered on one value of an
  attribute the parent was coloured by ("show only Department='Sales'" when colour
  encoded `Department`), every node in the subgraph now has the same colour. The
  legend is meaningless. Reset node colour to uniform with
  `visualization_reset_style`.
- **Preserve the channels that still mean something.** In the case above, if size
  was mapped to `degree_centrality`, keep it — it is a different attribute and
  still varies. Reset only the channel that collapsed.

If a metric drives an encoding and the subgraph's topology differs, the values
attached to nodes are the parent's. Recompute the metric on the subgraph before
relying on it, and say that the numbers changed (see `analysis-planning`).

## Getting back out

- `switch_to_parent_network` — one level up the subgraph tree.
- `switch_to_main_network` — all the way back to the original full graph.
- `visualization_switch_network(network_id=...)` — jump to any network by id;
  use `subgraph_list` to see what exists.

## Typical procedure: "Austrian composers, then just the main component"

1. `subgraph_create_by_filter(conditions=[...])` — the attribute filter.
2. `subgraph_largest_component(network_id=<id from step 1>)` — note this runs on
   the *new* subgraph, not the original graph.
3. `visualization_switch_network(network_id=<id from step 2>)`.
4. Reset node colour if step 1 filtered on the attribute that colour encodes.
5. Report both steps and the resulting node/edge counts.

## Typical procedure: "focus on these nodes"

1. `subgraph_create_from_nodes(node_ids=[...], preserve_layout=True)`.
2. `visualization_switch_network(network_id=NEW_ID)`.
3. Report: "Focused on N nodes, keeping their positions from the full graph."
