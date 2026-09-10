---
name: analysis-planning
description: How to turn an open-ended analysis request into concrete strategies, and how to verify attributes exist before relying on them. Load this for "analyze this network" style requests, or before computing a metric or community structure.
triggers: [analyze, analyse, 分析, 特徴, 傾向, 構造, structure, important, 重要, influential, 中心, community, コミュニティ, クラスタ, cluster, group, グループ, centrality, 中心性, metric, 指標, attribute, 属性]
related_tools: [network_list_node_attributes, network_list_edge_attributes, analysis_louvain_communities, analysis_greedy_modularity_communities, analysis_label_propagation_communities, ask_user, analysis_degree_centrality, analysis_pagerank, analysis_betweenness_centrality, node_get_top_ranked, analysis_core_number, analysis_triangles, analysis_edge_betweenness, analysis_modularity]
---

## Offer distinct readings, not arbitrary ones

An open-ended request ("analyze this network", "show me the important parts") has
several genuinely different answers. Picking one at random hides the choice from
the user. Instead, name 2–3 strategies that answer *different questions*, and let
them choose **through `ask_user`**, never only through a prose list:

Call the tool with `question` and one field: `id="analysis_goal"`,
`label="分析の目的"`, `kind="select"`, and 2–3 concise, concrete `options`.
For "どういう分析ができますか？", this form is part of the answer even if the user
never mentioned UI. Explain the alternatives briefly if helpful, then call the
tool and stop. `allow_other` defaults to true: the UI adds その他（自由入力）;
do not spend one of the three candidate slots on "その他".

Example on a graph with `club`: offer "clubごとのつながりを比較",
"次数で中心的なノードを探す", "構造上のコミュニティを調べる".
Adapt to the current graph; never invent attributes. A user's free-text answer
can replace all suggestions. Do not infer that displaying a choice approves it.

The distinct readings are:

- **Structural**: how the graph is organised — community detection, connected
  components, k-core decomposition.
- **Positional**: which nodes matter, and in which sense — degree (local
  connections), betweenness (bridges between groups), PageRank / eigenvector
  (connection to other well-connected nodes), closeness (reach).
- **Attribute-based**: how existing metadata distributes over the structure — do
  the graph's own attributes (`club`, `country`, `type`, `year`) line up with
  its shape?

Ground the options in what this network actually has. The
`[Current Network Context]` block lists the real attributes; an option that
depends on an attribute the graph does not have is not an option.

Keep it to two or three. A list of six is a worse interface than the WIMP menu
this system replaces.

## Prefer existing attributes over computing new ones

When the user asks about "groups", "clusters", "types", or "categories", look at
the string/categorical attributes in `[Current Network Context]` **first**. If
one already represents the requested grouping — `club`, `department`, `genre` —
use it. Running community detection to rediscover a grouping the data already
records produces a different, harder-to-explain answer to the question the user
asked.

Compute a community structure when the user wants the *structural* grouping
specifically, or when no attribute encodes what they asked about.

## Verify attributes before using them

Any operation keyed on an attribute — colour, size, labels, filter, sort, top-N —
needs the exact stored name, and names are case-sensitive.

1. `[Current Network Context]` at the end of the system prompt already lists node
   and edge attributes and is always present. Read it there first.
2. Call `network_list_node_attributes` / `network_list_edge_attributes` only when
   that is not enough: the list was truncated, or an attribute was created
   mid-conversation.
3. If the user's word does not match a stored name, do not force it. "Nationality"
   when the data has `citizenship` means you use `citizenship`. If several
   attributes could plausibly match, ask which one they mean.

A styling call with a non-existent attribute is refused before it runs, and the
refusal lists the real names — so a wrong guess costs a full round trip. Reading
the context block costs nothing.

## Metrics save under names you must read back

Persisting computation tools write their results as node attributes, and some names are
derived rather than fixed. Community tools save to
`{algorithm}_community` — `louvain_community`, not `community`. Always take the
attribute name from the tool's own return message rather than assuming one, then
use that exact string in the follow-up styling call.

## Metrics are topology-dependent

Degree, centrality, and clustering are properties of the graph they were computed
on. Extraction excludes derived metrics; do not assume the parent’s values were
copied or that they describe the new view. If a metric matters for analysing a
subgraph, recompute it there — and say that you did, since the numbers will differ
from the ones reported earlier.

## Typical procedure: "show me the community structure"

1. Run community detection. Read the returned message for the exact saved
   attribute name.
2. Colour nodes by that exact name with `scale_type='CATEGORICAL'`
   (see `visual-encoding`).
3. Report the community-to-colour mapping using the hex codes from the legend.
4. If useful, follow with the size of each community or the nodes bridging them
   (`analysis_betweenness_centrality`).

## Algorithm-specific controls

Prefer the separate Louvain, greedy-modularity, and label-propagation tools.
Louvain offers resolution, seed, gain threshold, and level limit. Greedy modularity
has cutoff/best_n instead of a seed; exactly k groups requires both set to k.
Semi-synchronous label propagation has no weight or seed parameter. Do not silently
switch algorithms on failure. Community numbers are labels, not rankings.

PageRank accepts personalization, dangling-node distribution, initial ranks, and
convergence controls. Read the exact saved `pagerank` attribute. Distinguish
incoming from outgoing centrality on directed graphs; closeness uses incoming
paths. Use `ask_user` when the direction or meaning of an edge value is unclear.


## Read-only structural measurements

`analysis_core_number` measures cohesive cores without extracting one.
`analysis_triangles` counts local closure; `analysis_transitivity` measures global
closure. `analysis_edge_betweenness` measures edge shortest-path traffic and takes
distances, not strengths. `analysis_modularity` evaluates an existing partition;
keep graph, weight, and resolution fixed when comparing partitions. These tools
return values without saving attributes or changing the view. Do not pass their
result field names to a styling tool as if those were stored attributes.
