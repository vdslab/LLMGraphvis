---
name: view-navigation
description: Focusing on nodes, showing a route or a neighbourhood, and zooming the view — without extracting a subgraph. Load before any "focus on / show the path / zoom in / zoom out" request.
triggers: [focus, フォーカス, 注目, 着目, 注視, 強調, highlight, ハイライト, 目立たせ, 浮き上が, 薄く, dim, zoom, ズーム, 拡大, 縮小, 寄って, 寄せ, 近づ, 引いて, 引きで, 全体を表示, 全体表示, 全体が見え, 見えるように戻, 表示を戻, ズームを戻, 元の表示, 全体を見, 元に戻, 画面に収め, zoom out, show everything, show the whole, fit to screen, 経路を表示, パスを表示, 経路を見, ルート, route, show the path, 近傍, 隣接, 周り, 周辺, neighborhood, neighbourhood, neighbors]
related_tools: [node_search, visualization_highlight, visualization_set_viewport, visualization_reset_style, visualization_set_node_labels, analysis_shortest_path, analysis_k_shortest_paths, node_get_neighbors, node_common_neighbors, visualization_get_state]
---

## Look, don't cut

Focusing on part of the network is a **view** operation. Use
`visualization_highlight`: the rest of the network stays on screen, dimmed,
and every later analysis still runs on the whole network.

Extract a subgraph (`subgraph-workflow`) only when the user wants later
analysis *restricted* to the subset ("only these", "analyse this group on its
own", "remove the rest"). If a request could mean either, prefer the highlight;
it is reversible with one call and loses nothing.

## Choose the edges

| The user wants | `edges` | Extra |
|---|---|---|
| These nodes and how they connect to each other | `induced` | |
| The route from A to B | `path` | `node_ids` = the returned `path`, in order |
| A node and everything it touches | `incident` | `neighbor_hops` to include the neighbours |
| Just mark the nodes | `none` | |

`color` overrides the encoding of the highlighted nodes. Leave it unset when a
colour channel already carries meaning the user still needs to read.

## Procedures

### Focus on named nodes
1. Resolve names with `node_search`; ask with `ask_user` if a name is ambiguous.
2. `visualization_highlight(node_ids=[...], zoom_to=True)`.
3. Say what is highlighted and that the rest is dimmed, not removed.

### Show a route
1. `analysis_shortest_path` (one route) or `analysis_k_shortest_paths`
   (alternatives). Mind cost semantics — see `path-analysis`.
2. `visualization_highlight(node_ids=<path>, edges='path', zoom_to=True)`.
   For alternatives, highlight the one the user picks, or the first and
   mention the others with their hops/costs.
3. Report hops and total cost. To label the route, call
   `visualization_set_node_labels(visibility='highlighted')` in the same response.

### Show a neighbourhood
`visualization_highlight(node_ids=[id], neighbor_hops=1, edges='incident',
zoom_to=True)`. Use `node_get_neighbors` only when the user wants the list
itself, and `node_common_neighbors` for "what do A and B share".

### Zoom
- "Zoom in on X": `visualization_set_viewport(target='nodes', node_ids=[...])`.
- "Zoom to what is highlighted": `target='highlighted'`.
- "Zoom out / show everything / back to the whole view": `target='all'`. This
  is also the only undo for a `zoom_to=True` highlight: the zoom is not a style,
  so `visualization_reset_style` never moves it.
The move happens once; the user can pan and zoom freely afterwards. Layout
`scale`/`center` are not a zoom.

### Clear the focus
`visualization_reset_style(targets=['highlight'])`. A new highlight replaces the
old one, so there is no need to clear before highlighting something else.

## Composition

A highlight persists across colour, size and label changes until it is reset
or replaced. It composes with every encoding: e.g. colour by community, then
highlight one route to see which communities it crosses.
