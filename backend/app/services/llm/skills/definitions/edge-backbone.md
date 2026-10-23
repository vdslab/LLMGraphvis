---
name: edge-backbone
description: Dense networks that draw as a hairball (layout_quality reports `dense_edges`, or every node links to many others) — why no layout parameter fixes it, how to offer an edge backbone that keeps every node and only its strongest ties, and how to draw and read the result.
triggers: [hairball, ヘアボール, 毛玉, dense, 密集, 密すぎ, 線が多, エッジが多, too many edges, backbone, バックボーン, 間引, thin out, sparsify, similarity network, 類似度, まとまりが見え, groups do not separate, 塊]
related_tools: [subgraph_suggest_reduction, subgraph_edge_backbone, network_select, layout_profile, layout_spring, layout_forceatlas2, visualization_generate, visualization_set_edge_color, visualization_set_node_color, analysis_connected_components, ask_user, switch_to_parent_network]
---

## Recognise it

`layout_quality.issues` contains `dense_edges` when the drawn network has so many
edges per node that they cover the canvas. Similarity and co-occurrence networks
(documents, courses, co-purchases) are typical: each node links to every item
that is somewhat alike, with near-uniform weights.

Under `dense_edges` no layout parameter separates the groups: the layout sees an
almost uniform graph. Do not offer a parameter search, a tuning panel or
another algorithm as the fix; say plainly that the edges, not the layout, hide
the structure.

## Offer, do not decide

Thinning edges changes what later metrics are computed on, so the user chooses
(`network-reduction` applies).

1. Call `subgraph_suggest_reduction`. Its `edge_backbone` candidates keep every
   node and only each node's k strongest edges, and report for each k the edges
   left, the connected parts and the largest part.
2. Explain the candidates in the user's words: fewer kept edges show tighter
   groups and more small separate parts; more kept edges keep the ties between
   groups. Name the strength used (imported weight, or shared neighbours when
   the network has no weights).
3. Offer keeping the whole network too, with fainter edges
   (`visualization_set_edge_color` with a low `opacity`) as the light-touch
   option.
4. Ask with `ask_user` in the same response as the explanation.

## After the user chooses a backbone

1. `subgraph_edge_backbone` with the chosen candidate's arguments.
2. `network_select` with its `created_network_id`.
3. Lay it out with the first layout `layout_profile` recommends for it, then
   `visualization_generate`. On a large network that is `layout_spring`:
   ForceAtlas2 has to stop early there and leaves an even disc, which looks
   like the hairball the user wanted gone.
4. Re-apply the encoding the user had (the backbone is a new network), e.g. the
   same categorical colour, and keep edges faint so the groups read first.
5. Report: edges kept out of the original, how many parts, what the largest
   part and the small parts are made of (compare with the colour attribute),
   and that degrees and centralities on it describe the thinned network.
   `switch_to_parent_network` returns to the full one.
