---
name: error-recovery
description: Diagnosing tool failures and policy refusals, and knowing when to stop retrying and report to the user. Load this after a tool returns an error or a blocked_by field.
triggers: [error, エラー, 失敗, failed, not found, 見つから, 存在しない, blocked, ブロック, 拒否, invalid, 無効, retry, 再試行, やり直]
related_tools: [node_search, network_list_node_attributes, network_list_edge_attributes, visualization_get_state]
---

## Two kinds of failure, handled differently

**A tool error** means the call was attempted and something went wrong. The
result has an `error` field.

**A policy refusal** means the call was never attempted: a pre-execution check
rejected it. The result has both `error` and **`blocked_by`** naming the check.
This is not a bug and not a transient failure — retrying the identical call will
be refused identically. The `error` text states what to do instead; do that.

The refusals you can encounter:

- **Attribute does not exist** — the message lists the network's real attribute
  names. Pick the right one from that list. If none is what the user meant, ask
  them; do not substitute something approximate.
- **Ambiguous attribute** — two attributes differ only by case. Ask which.
- **Computation too expensive** — the graph is above the size limit for a
  super-linear algorithm. The message names the mitigation: an approximation
  parameter (`k` for betweenness), a cheaper metric, or extracting a smaller
  subgraph first. Choose one, and tell the user which and why — they should know
  they got an approximation rather than an exact figure.
- **Repeated identical call** — you have already made this exact call. Use the
  result you already have.

## Diagnosing real errors

- **Node not found** — you probably used a label where an ID is required. Use
  `node_search(query=...)` to resolve the label to an ID, then retry with the ID.
- **Attribute not found** (from the tool rather than a guard) — the attribute may
  have been created mid-conversation under a derived name. Re-list attributes;
  for a computed metric, re-read the computing tool's return message for the
  exact name it saved.
- **Invalid parameter value** — read the tool's schema for the accepted range.
  Out-of-range numbers are usually clamped automatically and reported back via
  `_adjusted_arguments`; an outright rejection means the value was the wrong
  *kind*, not just too large.
- **Layout failed on this graph** — some layouts have structural preconditions.
  `layout_planar` requires a planar graph; `layout_bipartite` and
  `layout_multipartite` require a valid partition attribute. Fall back to a
  force-directed layout and say why.
- **Empty result** — a filter that matched nothing is not an error. Report that
  no nodes matched, and suggest a looser condition rather than silently showing
  an empty graph.

## Correct once, then stop

Attempt one targeted correction based on what the error actually said. Do not
retry the same call unchanged, and do not cycle through variations hoping one
works.

After three failures of the same tool the turn is ended for you and the user is
told why. Reaching that point means the diagnosis was wrong, so it is better to
stop earlier and ask: report what you tried, quote the specific error, and say
what you need from the user to proceed.

## Report failures honestly

State that the operation did not succeed, what the error was, and what you did
about it. Do not describe a fallback as if it were what was asked for, and do not
report partial completion as completion. If half of a multi-step request worked,
say which half.
