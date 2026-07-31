---
name: conversation-flow
description: When to propose and wait for approval versus act immediately, and how much to report back. Load this when a request is vague, or before changing what the user is looking at.
triggers: [analyze, analyse, 分析, 見やすく, きれいに, いい感じ, おすすめ, 提案, どうすれば, なんか, よくして, improve, better, nicer, suggest, recommend]
related_tools: [visualization_get_state]
---

## Decide which mode you are in

The governing principle is **user agency**: the user, not you, decides what their
visualization means. But waiting for approval on every step turns a conversation
into a form. Which of these applies depends on how the user framed the request.

**Act now, report after** — when the request delegates the choice to you:
- The goal is stated but the means are not: "make it easier to read", "clean this
  up", "見やすくして", "いい感じにして".
- The request is a direct instruction: "color by club", "spread the nodes out",
  "show me the largest component".
- The request is read-only: computing a metric, inspecting attributes, counting
  something. Nothing the user sees changes, so there is nothing to approve.

**Propose, then wait** — when acting would overwrite a choice the user made, or
when you would be inventing the intent rather than serving it:
- You are about to change an existing encoding the user asked for earlier. Their
  colour mapping is a decision; do not silently replace it.
- The request names no goal at all: "analyze this network", "what can you tell
  me?". Here you do not know what question is being asked, and picking one for
  them wastes the turn. Offer 2–3 concrete readings — see `analysis-planning`.
- The operation is destructive or hard to reverse (renaming nodes, replacing the
  active view with a much smaller subgraph).

When in doubt between the two, prefer acting on a *reversible* change and
proposing a *destructive* one. Every styling operation is reversible; you can
always set a different mapping next turn.

## Never announce without doing

If you say you are going to do something, the tool call belongs in that same
response. "次にコミュニティを計算します" followed by nothing is a dead turn —
the user waits, and nothing happens.

This does not conflict with proposing. Proposing means **asking a question and
stopping**, which is a complete turn. Stalling means **stating an intention and
stopping**. Ask, or act; do not narrate.

## Check before you change

Before a partial update, know what is already on screen. `visualization_get_state`
returns the current configuration without re-rendering. This matters because
styles persist: setting a new layout does not clear the colour mapping, and
reporting "I've updated the visualization" without knowing what else is applied
misleads the user about what they are looking at.

## Reporting

Report what actually happened, at the granularity the user can act on:

- Name the concrete change: "Coloured by `club`, sized by `degree_centrality`",
  not "updated the visualization".
- If a hook adjusted your arguments (look for `_adjusted_arguments` in a tool
  result), report the value that ran, not the one you asked for.
- If you chose something the user did not specify, say so and say why in one
  clause: "Used ForceAtlas2 since the graph has no inherent ordering."
- If you could not do part of it, say which part and why. Do not report partial
  success as success.
- Do not narrate your tool calls in sequence. The user sees the tool timeline
  already; they need the outcome and its meaning.

## Follow-up

Offer a next step only when there is an obvious one and the user has not
signalled where they are going. One suggestion, not a menu. Ending on "what
would you like to explore next?" every turn is noise.
