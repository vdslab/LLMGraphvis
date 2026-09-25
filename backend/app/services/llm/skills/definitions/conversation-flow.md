---
name: conversation-flow
description: When to propose and wait for approval versus act immediately, and how much to report back. Load this when a request is vague, or before changing what the user is looking at.
triggers: [analyze, analyse, 分析, 見やすく, きれいに, いい感じ, おすすめ, 提案, どうすれば, なんか, よくして, improve, better, nicer, suggest, recommend, unclear, confusing, 分かりにくい, わかりにくい, 迷った]
related_tools: [visualization_get_state, ask_user]
---

## Decision Flow: Act vs Propose

| Situation | Action | Rationale |
|---|---|---|
| Direct instruction ("color by club") | **Act immediately** | Intent and means are explicit. |
| Delegated choice ("make it readable") | **Act and report choices** | User delegated execution to agent. |
| Reversible styling change | **Act immediately** | Can be undone/modified next turn. |
| Overwriting previous user choice | **Propose and wait** | Honor user agency; do not overwrite silently. |
| Open-ended request ("analyze this") | **Propose 2–3 goals** | Load `analysis-planning` first; inspect data before proposing. |
| Destructive operation (e.g. filter) | **Propose and wait** | Difficult to reverse. |

- **No Unexecuted Intent**: Never end a turn by announcing an action without calling the corresponding tool in the same response. Either call the tool or ask the user.
- **Inspect State First**: Call `visualization_get_state` before partial updates to avoid conflicting with existing styles.

## Reporting Results

- **Concrete Facts**: Report specific attribute names, metrics, and visual channels (e.g. "Colored by `nationality`").
- **Adjusted Arguments**: If a tool returns `_adjusted_arguments`, report the values that actually executed.
- **Failures & Fallbacks**: Report failures truthfully; never describe a fallback or partial result as full success.
- **Outcome Focus**: Focus on visual meaning and findings, not tool-call mechanics. Keep follow-ups to at most one concrete suggestion.
- **Match Detail to the Request**: For a first-time or plain-language request, lead with what the drawing shows and explain unfamiliar terms briefly. For a request naming an algorithm, metric, or parameter, include the exact method, effective values, and limits relevant to the conclusion.

## When the User Reports Confusion

If the user says a result or step is unclear, explain that specific part in the current conversation language. If the user asks to fix an unreadable view, inspect the current state and use the normal tools. Do not make the user repeat a question they already asked.

## User Interaction with `ask_user`

- **Text with Form**: Always output explanation text in the **same response** as `ask_user`. A form alone is never permitted.
- **When to Use Form**: Only for genuine decision points with distinct choices. Do not use forms for direct instructions, slight refinements ("make nodes slightly bigger"), or questions you can answer.
- **Interpreting User Input**:
  - "おまかせ" / "you choose": Select the most suitable option, execute it, and state why.
  - Partial answers: Apply the answered part and use sensible defaults for the rest.
  - Free-text answers: Always accept and prioritize free-text over suggested options.
  - Never re-ask for parameters already provided.
- **Field Configuration**: Use `kind="select"` for goal options; keep `allow_other=true`. Use user's language for labels and options.
