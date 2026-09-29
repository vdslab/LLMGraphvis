---
name: labels
description: Choosing what text nodes show, which nodes get a permanent label, and how labels look (size, truncation). Load before any label request.
triggers: [label, labels, ラベル, 名前, 名称, ノード名, 表示名, テキスト, font, フォント, 文字サイズ, 読め, 省略, 長い名前, truncate, 重なる, 名前を出, 名前を表示, 名前を消, annotate, 注記]
related_tools: [visualization_set_node_labels, visualization_reset_style, visualization_get_state, network_list_node_attributes, node_search, visualization_highlight]
---

## What a label call controls

`visualization_set_node_labels` sets the whole label channel at once:

- **text** — `attribute`: show that attribute's value instead of the node's name.
- **which nodes** — `visibility`:
  - `auto`: all nodes of a small network, only the best-connected of a large one.
  - `top_n` + `rank_by`: the most important nodes by a metric the user cares
    about (compute it first; read its saved name from the tool result).
  - `nodes` + `node_ids`: exactly the nodes the user named.
  - `highlighted`: whatever `visualization_highlight` currently emphasizes.
  - `all` / `hover`.
- **look** — `font_size` (screen pixels, constant while zooming) and
  `max_length` (longer text is shortened; the tooltip keeps the full text).

Omitted parameters return to their defaults, so restate everything that should
stay (e.g. keep `attribute` when only changing `visibility`).

## Choosing

- The user asks to "show names" on a large network: `auto`, or `top_n` with a
  metric that matches their question. Labelling every node of a large network
  is unreadable; say so and offer `top_n` instead.
- The user names nodes: `nodes`.
- A route or focus is on screen: `highlighted`.
- Long names (titles, descriptions): set `max_length`.
- "Too small / can't read": raise `font_size`; "too crowded": label fewer
  nodes or zoom in (`view-navigation`). Overlapping labels are thinned
  automatically, so a dense view shows fewer labels than requested — tell the
  user when `label_style.labeled_count` is much larger than what fits.

## Reset

`visualization_reset_style(targets=['node_label'])` returns labels to the
default, where the user's Labels button decides.
