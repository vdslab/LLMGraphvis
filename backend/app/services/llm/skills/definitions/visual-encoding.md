---
name: visual-encoding
description: Choosing which visual channels encode which attributes, combining colour and size into one readable view, picking the right scale_type, and reporting the resulting legend. Load this before any colour, size, or label change.
triggers: [color, colour, 色, 色分け, カラー, size, サイズ, 大きさ, 凡例, legend, encode, マッピング, mapping, highlight, 強調, 目立, gradient, グラデーション, uniform, リセット, reset, combine, 組み合わせ, 同時, 両方, 併用, 複数, multiple, both, エッジ, edge colo, edge width, リンクの, 太さ, 太く, 細く, 薄く, 透明, opacity, transparen, 対数, logarithm, log scale, 外れ値, outlier, 色の違い, 差が分から, 差がわから, 見分け]
related_tools: [visualization_set_node_color, visualization_set_node_size, visualization_set_node_labels, visualization_set_edge_color, visualization_set_edge_width, visualization_get_state, visualization_reset_style, analysis_betweenness_centrality, analysis_degree_centrality, apply_parameter_tuning, visualization_generate]
---

## Channel Mapping Rules

- **Color (Categorical)**: Discrete categories (`club`, `country`, `louvain_community`).
  Use `scale_type='CATEGORICAL'`. Palette is auto-assigned (`tableau10` for <=10, `paired` for 11-12, `extended20` for >12). Supply `mapping` only for explicit user colors.
- **Color (Sequential)**: Continuous metrics (`degree_centrality`, `pagerank`, `year`).
  Use `scale_type='LINEAR'`. Optional `gradient` as hex list low-to-high.
- **Color (Ranking)**: Top-N emphasis ("top 10 nodes").
  Use `scale_type='RANKING'` with `ranking_rules=[{"top": N, "color": "#HEX"}]`.
- **Size**: Exactly one continuous quantity (importance/weight).
  Rendered radius is area-proportional: $r = \sqrt{\text{size} \times 10 / \pi}$. To double visual diameter, roughly quadruple `max_size` (~4x area).
- **Labels**: Node identity. Which nodes are labelled, their size and truncation: load `labels`.
- **Highlight a specific set or route**: not a colour mapping — use `visualization_highlight` (`view-navigation`). `RANKING` is for "top N by a metric".
- **Edge Color / Width**: Edge attributes (`weight`). Use sparingly to avoid visual clutter.
- **All edges at once** ("fainter / thinner edges"): omit `attribute`. `visualization_set_edge_color(opacity=...)` changes how strongly edges show; `visualization_set_edge_width(default_width=...)` their width. Restate `attribute` to keep an existing edge mapping.

## Skewed Values and Outliers

A numeric mapping spreads values linearly by default. When a few nodes have much larger values (typical of centrality), every other node gets nearly the same colour or size. The legend's range and the user's complaint ("all the same colour", "色の違いがわからない") are the signal.

- `transform='log'`: keeps the values' order and magnitude but compresses the top. The default fix for a skewed metric.
- `transform='rank'`: spreads nodes evenly by order. Use when only the order matters.
- `value_max` / `value_min`: values beyond are drawn like the end. Use when the user wants the bulk of nodes distinguished and the outliers simply marked as "at least this much".

Experts may name these directly; a beginner's complaint is reason enough to apply `log`, then say in one sentence that the colours now follow a log scale. The same three parameters work on node size and on edge colour and width. They persist with the channel; pass `transform='linear'` to undo.

## Composite Encodings (Multiple Channels)

Channels are independent and compose on the same canvas. Setting one channel preserves all others.
When the user's intent involves multiple aspects (e.g. affiliation + importance), encode both in the **same response**.

| User Goal | Color Channel | Size Channel | Reading Supported |
|---|---|---|---|
| Group affiliation & broker | Categorical (`club`, `genre`) | `betweenness_centrality` | Groups and who bridges them |
| Community structure & hub | `{algorithm}_community` | `degree_centrality` or `pagerank` | Clusters and their key nodes |
| Classification vs topology | Recorded category | Label with community | Agreement between data and structure |
| Top-N highlight & distribution | `scale_type='RANKING'` | Metric (e.g. `degree_centrality`) | Outliers against general spread |

- **Channel budget**: 2 node channels (color + size) is the readable default; 3 (plus label or edge width) is the ceiling.
- **No double-encoding**: Never encode the same attribute on both color and size.
- **Batching**: Independent tool calls in one model turn (`visualization_set_node_color` + `visualization_set_node_size`) execute in a single round. Compute prerequisite metrics first.

## State Preservation & Reset

- Each `visualization_set_*` call updates only its channel and preserves others.
- Passing empty or omitted fields does **not** clear a style. Use `visualization_reset_style(targets=['node_color'])` to return to default uniform style (`'highlight'` clears a highlight).
- Calling the same `set_*` tool twice in one turn for different attributes replaces the first mapping; use different channels instead.

## Legend Reporting

- **Exact Hex Codes**: Report exact hex codes from the tool result `legend` (e.g. `Mr. Hi: #4e79a7`). Do not substitute subjective color names ("blue and red"), as the chat UI renders an inline color swatch for hex codes.
- **Sequential**: Report attribute name and value range: `pagerank from 0.003 (light) to 0.101 (dark)`.
- **Summary**: State each assigned channel and its combined analytical reading.

## Procedures

### Creating a Composite View
1. Check `[Current Network Context]` for existing/imported attributes.
2. Compute any missing metric (e.g. `analysis_betweenness_centrality`), reading the exact saved attribute name from the tool result.
3. In one response, call `visualization_set_node_color` and `visualization_set_node_size`. (No trailing `visualization_generate` needed; styling tools render automatically).
4. Report both legends with hex codes and describe the joint reading.

### Inspecting Current Style
1. Call `visualization_get_state` to inspect active encodings without re-rendering.
2. Read the channel's legend and report with exact hex codes and attribute names.
