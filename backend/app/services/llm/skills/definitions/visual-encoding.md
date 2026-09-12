---
name: visual-encoding
description: Choosing which visual channels encode which attributes, combining colour and size into one readable view, picking the right scale_type, and reporting the resulting legend. Load this before any colour, size, or label change.
triggers: [color, colour, 色, 色分け, カラー, size, サイズ, 大きさ, label, ラベル, 凡例, legend, encode, マッピング, mapping, highlight, 強調, 目立, gradient, グラデーション, uniform, リセット, reset, combine, 組み合わせ, 同時, 両方, 併用, 複数, multiple, both]
related_tools: [visualization_set_node_color, visualization_set_node_size, visualization_set_node_labels, visualization_set_edge_color, visualization_set_edge_width, visualization_get_state, visualization_reset_style, analysis_betweenness_centrality, analysis_degree_centrality]
---

## Match the channel to the data

- **Colour, categorical** — unordered categories: `club`, `country`,
  `louvain_community`. Use `scale_type='CATEGORICAL'`. A palette is assigned
  automatically; supply `mapping` only when the user names specific colours.
  Supply `palette` when the user asks for a particular mood: `tableau10` is the
  balanced default, `category10` or `set1` is vivid, `set2` is softer, `dark2`
  is dark and saturated, and `pastel1`/`pastel2` is pale. `paired` is useful
  for 11–12 categories. Never invent a palette name; use one accepted by the
  tool schema.
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

## Channels compose: one question, several channels

Colour, size, label, edge colour and edge width are **independent channels on the
same drawing**. Assigning one does not consume the others, and every `set_*` call
preserves the channels it does not touch. A view with two channels is not twice
the work and not twice the clutter — it answers a two-part question in one image,
which is the whole reason this canvas exists.

So when the user's question has more than one part, encode more than one part.
"Which faction is each member in, and who holds the network together?" is two
questions: membership is categorical (colour) and holding-together is a
continuous quantity (size). Answering only the first, and leaving size uniform,
throws away the second half of what they asked.

The default pairing, and the one to reach for first:

> **one categorical attribute → colour, one continuous quantity → size.**

They read cleanly together because they use unrelated perceptual channels: hue
separates groups, area orders magnitudes. Layout position is a third channel you
already spent — a force-directed layout groups the densely connected, so colour
and size are read *against* that grouping ("the big node is coloured Officer but
sits inside the Mr. Hi cluster") — and that contrast is usually where the finding
is.

**How many at once.** Two node channels is the readable default; three
(plus labels, or plus edge width for `weight`) is the practical ceiling. Past
that the reader cannot hold the legend in their head, and each further channel
costs more than it adds. Prefer two channels that answer the question to four
that merely fill the slots.

**Cost.** Independent calls made in one response count as a single tool-calling
round, so build the whole encoding in one response — `visualization_set_node_color`
and `visualization_set_node_size` together — rather than one channel per turn.
Compute the metric first if it does not exist yet; the styling call needs the
attribute name from that tool's return message.

## Composite recipes

Each of these is a whole answer, not a step. Name the reading it supports when
you propose it or report it.

- **Recorded group × structural importance** — colour by the imported
  categorical attribute (`club`, `department`, `genre`), size by
  `betweenness_centrality`. Reads as: which group each node belongs to, and who
  brokers between the groups. This is the standard opening for a network with
  one meaningful categorical attribute, and the right answer to "I want to see
  the two opposing groups" — the colour shows the split, the size shows who
  spans it.
- **Detected community × activity** — colour by `{algorithm}_community`, size by
  `degree_centrality` or `pagerank`. Reads as: the structural grouping, and each
  community's hubs. Use when the data records no grouping of its own.
- **Recorded group × detected community** — colour by the imported attribute,
  label by the community attribute (or the reverse). Reads as: how far the
  structure agrees with the recorded categories. Two categorical channels only
  work when one of them is the label, never as colour twice.
- **Top-N highlight × magnitude** — colour by `scale_type='RANKING'` on a
  metric, size by the same *kind* of quantity measured differently
  (`ranking_rules` on `pagerank`, size by `degree_centrality`). Reads as: the
  shortlist, against the general distribution.
- **Any of the above + edge width by `weight`** — add only when the edge value
  carries meaning the user asked about. It is the first thing to drop when the
  view gets busy.

## Decoration, and what is not decoration

Every channel you assign must answer part of what the user asked. That is a bar
on decoration — not a limit of one channel.

- **Decoration**: assigning colours because the graph would "look better", or
  adding a size mapping when the user asked only to change the layout. Leave
  those uniform.
- **Not decoration**: a second channel that answers a second part of the
  question, or that you propose explicitly as part of an encoding and the user
  accepts. Proposing "colour by `club`, sized by betweenness" for "show me the
  two groups" is serving the request, not embellishing it.

Still do not **double-encode the same attribute** on two channels. Colouring
*and* sizing by `degree_centrality` conveys nothing beyond sizing by it, and
consumes a channel that could have carried a second variable. If you have only
one attribute worth showing, use one channel and say so.

## Size is an area, not a radius

The `size` value is treated as an area: the frontend renders each node with
radius `sqrt(size * 10 / π)`. So doubling `size` does **not** double the visible
diameter. When a user says "make the big nodes twice as big", they mean the
diameter, which means roughly quadrupling `max_size`. This convention is shared
across the tool descriptions, the builder, and `NetworkGraph.jsx`.

## Partial updates preserve everything else

Each `visualization_set_*` call changes one channel and leaves the others as they
were — the server re-loads any configuration you do not pass. This is deliberate:
it is what lets a conversation build an encoding up across several turns, and it
is why adding a channel never costs you the one already on screen.

Two consequences:
- To change only the colour, call only the colour tool. Do not re-send the size
  configuration "to be safe"; you may overwrite a value you did not intend to.
- Because unset means "keep", passing an empty value does **not** clear a channel.
  Use `visualization_reset_style` to actually return a channel to its default.

When a user asks to change one channel of a composite encoding ("make the sizes
more extreme", "use warmer colours"), call only that channel's tool. The rest of
the encoding stays, so do not rebuild it.

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

Report **every channel you set**, in one sentence each, then the reading they
support together:

> `club` の色分け（`Mr. Hi: #4e79a7` / `Officer: #f28e2c`）に、媒介中心性のノードサイズを重ねました。
> 大きくて境界付近にあるノードが、2つのクラブをつないでいる人です。

## Typical procedure: a composite encoding

1. Read `[Current Network Context]` for the exact attribute names and which of
   them were imported rather than computed.
2. Compute the metric you need for the size channel if it is not there yet, and
   take the saved attribute name from the tool's return message.
3. In one response, call `visualization_set_node_color` and
   `visualization_set_node_size` together. Do not follow them with
   `visualization_generate`; each one renders as part of its own work.
4. Report both legends and the joint reading.

## Typical procedure: answering "what does this colour mean?"

1. `visualization_get_state` — inspect the current configuration without
   re-rendering. Do not call `visualization_generate`, which would redraw for no
   reason.
2. Read the legend for the channel in question.
3. Answer with the attribute name and the specific hex code:
   "#4e79a7 is community 0, which has 17 nodes."
