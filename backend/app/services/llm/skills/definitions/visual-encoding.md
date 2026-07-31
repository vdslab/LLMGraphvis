---
name: visual-encoding
description: Choosing which visual channel encodes which attribute, picking the right scale_type, and reporting the resulting legend. Load this before any colour, size, or label change.
triggers: [color, colour, 色, 色分け, カラー, size, サイズ, 大きさ, label, ラベル, 凡例, legend, encode, マッピング, mapping, highlight, 強調, 目立, gradient, グラデーション, uniform, リセット, reset]
related_tools: [visualization_set_node_color, visualization_set_node_size, visualization_set_node_labels, visualization_set_edge_color, visualization_set_edge_width, visualization_get_state, visualization_reset_style]
---

## Match the channel to the data

- **Colour, categorical** — unordered categories: `club`, `country`,
  `louvain_community`. Use `scale_type='CATEGORICAL'`. A palette is assigned
  automatically; supply `mapping` only when the user names specific colours.
- **Colour, sequential** — continuous quantities: `degree_centrality`,
  `pagerank`, `year`. Use `scale_type='LINEAR'`, optionally with `gradient` as a
  list of hex codes from low to high.
- **Colour, ranking** — when the interesting thing is *position in an ordering*
  rather than the value itself ("highlight the top 10"). Use
  `scale_type='RANKING'` with `ranking_rules`.
- **Size** — one continuous quantity, ideally the one the user calls
  "importance". Only ever one; two competing size signals cannot be read.
- **Labels** — identity. Showing all labels on a large graph produces an
  unreadable mass; leave `show_all=False` and label selectively unless the graph
  is small or the user asks.
- **Edge colour / width** — edge attributes such as `weight`. Use sparingly:
  edges are thin and numerous, and encoding on them is much harder to read than
  on nodes.

Do not double-encode the same attribute on two channels. Colouring *and* sizing
by `degree_centrality` conveys nothing beyond sizing by it, and consumes a channel
that could have carried a second variable.

Do not decorate. If the user asked only for a layout change, do not also assign
colours because the result would "look better". Uniform is the correct default.

## Size is an area, not a radius

The `size` value is treated as an area: the frontend renders each node with
radius `sqrt(size * 10 / π)`. So doubling `size` does **not** double the visible
diameter. When a user says "make the big nodes twice as big", they mean the
diameter, which means roughly quadrupling `max_size`. This convention is shared
across the tool descriptions, the builder, and `NetworkGraph.jsx`.

## Partial updates preserve everything else

Each `visualization_set_*` call changes one channel and leaves the others as they
were — the server re-loads any configuration you do not pass. This is deliberate:
it lets a conversation build up an encoding across several turns.

Two consequences:
- To change only the colour, call only the colour tool. Do not re-send the size
  configuration "to be safe"; you may overwrite a value you did not intend to.
- Because unset means "keep", passing an empty value does **not** clear a channel.
  Use `visualization_reset_style` to actually return a channel to its default.

## Report the legend with real hex codes

After a colour change, read the `legend` in the tool result and report the
mapping using the **exact hex codes it contains**:

> `Mr. Hi: #4e79a7`, `Officer: #e15759`

Not "blue and red". Two reasons: the palette has 20 entries and many are not
nameable ("#76b7b2" is not "green" in any useful sense), and the chat UI renders
a colour swatch inline next to any hex code you write — so quoting the real value
gives the user an accurate preview and a wrong colour name actively misleads them.

For a sequential mapping, report the attribute and its range rather than
enumerating colours: "`pagerank` from 0.003 (light) to 0.101 (dark)".

## Typical procedure: answering "what does this colour mean?"

1. `visualization_get_state` — inspect the current configuration without
   re-rendering. Do not call `visualization_generate`, which would redraw for no
   reason.
2. Read the legend for the channel in question.
3. Answer with the attribute name and the specific hex code:
   "#4e79a7 is community 0, which has 17 nodes."
