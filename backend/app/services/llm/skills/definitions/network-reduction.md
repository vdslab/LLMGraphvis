---
name: network-reduction
description: When the network is large (marked "large network" in the context), offer measured ways to shrink it and let the user choose; never shrink on your own. Load on a large network's first analysis turn, before a costly computation on it, or when the user says it is too big or cluttered.
triggers: [reduce the network, reduction, too large, too big, too many nodes, cluttered, hairball, simplify, 削減, 間引, 縮小, 大きすぎ, 多すぎ, ノードが多, 重い, ごちゃごちゃ, 見づらい, 簡略]
related_tools: [subgraph_suggest_reduction, subgraph_edge_backbone, subgraph_largest_component, subgraph_k_core, subgraph_high_degree_nodes, subgraph_extract_filter, network_select, visualization_highlight, visualization_set_viewport, ask_user, switch_to_parent_network, switch_to_main_network]
---

## What "large" means here

`[Current Network Context]` marks a network as large when its default layout
had to be cut short to finish in reasonable time. At that size the drawing is
dense, and costly analyses (betweenness, Kamada-Kawai, layout searches) take
minutes. The size is a property of the data, not a problem the user asked you
to fix.

When the network is dense rather than big (`layout_quality` reports
`dense_edges`), dropping nodes does not help: the `edge_backbone` candidates
keep every node and thin the edges; follow `edge-backbone`.

## When a reduction is harmless

Whether a loss matters depends on what the user wants to know. Match the
question to the `impact.issues` it cannot tolerate:

| The user wants to see | Do not offer candidates with | Why |
|---|---|---|
| hubs, the most connected or central nodes | (most cuts are fine) | the hubs are what is kept |
| groups, clusters, how groups compare | `drops_groups`, `skews_groups` | a missing or shrunken group reads as small or absent |
| paths, distances, reachability, bridges | `fragments` | cut links change every path and distance |
| the whole picture, counts, distributions | any node-dropping candidate | every statistic would describe a part |
| isolated, peripheral or rare nodes | any node-dropping candidate | the cuts drop exactly these |

A candidate with no issues still drops nodes; say which. Degree in a
similarity network (each node linked to its most similar ones) counts how many
others resemble a node, not how important it is; a degree cut there keeps
generic nodes, not key ones. For a question that only needs a part of the
drawing, highlighting it is usually better than any cut.

## Offer, do not decide

Reducing changes what every later number is computed on, so it is the user's
choice. Raise it once:

- on the first analysis turn of a large network, alongside answering what was
  asked, not instead of it;
- before starting a costly computation on a large network;
- when the user says the network is too big, slow or cluttered.

If the user declined or already chose, do not raise it again in that
conversation unless they ask.

## How to offer

1. Call `subgraph_suggest_reduction`. Pass `target_nodes` only if the user
   named a size.
2. Read each candidate's `impact` against the user's question (next
   section). Offer the two or three that lose nothing the question needs, and
   say for each, in the user's words: how many nodes and edges remain, what is
   dropped, what it costs (from `impact`: pieces cut apart, groups dropped or
   kept unevenly) and what that means for this data (e.g. dropping isolated
   courses, keeping only hub teachers). A recorded categorical attribute that
   matches the question (one department, one year) is often the most
   meaningful cut.
3. Always offer keeping the whole network as one of the choices. Mention that
   looking at a part without removing anything is possible with
   `visualization_highlight` or `visualization_set_viewport`. When every
   candidate costs something the question needs, say so and recommend keeping
   the whole network.
4. Ask with `ask_user` in the same response as the explanation, and wait.
   Do not call an extraction tool before the answer.

## After the user chooses

- Call exactly the tool and arguments the chosen candidate names. For
  `subgraph_extract_filter`, put the chosen values in `categories`.
- The legacy tools (`subgraph_largest_component`, `subgraph_k_core`,
  `subgraph_high_degree_nodes`) switch to and draw the new network themselves,
  keeping the parent's positions; offer a fresh layout, since positions from
  the dense parent rarely suit the smaller network. For the atomic
  `subgraph_extract_filter`, follow `subgraph-workflow`.
- Say plainly that results from now on describe the reduced network, and that
  `switch_to_parent_network` returns to the whole one. Relay the tool result's
  "Reduction impact" line in the user's words.
