---
name: parameter-tuning
description: Adjusting parameters from the user's words ("a bit finer", "spread it out", "resolution 1.3", "the previous one was better"), and attaching an expert tuning panel to parameter-sensitive results. Load this when a request changes how an existing result was computed or laid out.
triggers: [parameter, parameters, tune, tuning, adjust, slider, resolution, finer, coarser, spread, previous, パラメーター, パラメータ, 調整, 解像度, 細かく, 粗く, もう少し, もっと, 半分, 倍, 広げ, 狭め, さっき, 戻して, スライダー]
related_tools: [offer_parameter_tuning, apply_parameter_tuning, visualization_get_state, analysis_louvain_communities, analysis_greedy_modularity_communities, layout_forceatlas2, layout_spring, layout_suggest_parameters, visualization_set_node_size, visualization_generate]
---

## Words Are the Main Path

Users tune by saying what they want. Turn that into concrete values and act; the panel is only a shortcut for users who think in parameter names.

1. **Active panel?** If the system prompt has an `Active Parameter Tuning` block, call `apply_parameter_tuning` for any change to its pipeline tools, including arguments that are not panel fields. Do not call the pipeline tools directly for these changes.
2. **No panel**: re-run the tool with the changed argument (and the encoding/render step it needs, see `layout` and `visual-encoding`). Consider offering a panel afterwards (below).
3. **Convert words to numbers** from the current value, the explored range and the low/high meaning:
   - Explicit values and ratios ("1.3", "half", "double") are used as given, clamped to the range.
   - "a bit / 少し" = 1–2 steps (about 10% of the range); "much / more / もっと / かなり" = about 30%; "max / min" = the range ends.
   - "the previous one / さっきの方" = the `before` value of the latest change in the history.
   - Direction comes from the low/high labels and the tool's parameter description (e.g. higher `resolution` = smaller communities; higher `scaling_ratio` or lower `gravity` = more spread).
4. **Several requested changes go in one call**, so the pipeline re-runs once.
5. **Ambiguous is not a question.** Apply your best reading, state what you chose, and invite a correction. Do not use `ask_user` for parameter values.
6. **Report like an expert would read it**: parameter name, before → after, and what visibly changed (e.g. "`resolution` 1.0 → 1.3: 8 → 11 communities").

## Attaching a Tuning Panel

Offer `offer_parameter_tuning` in the same turn when the result depends strongly on a few parameters and the user is likely to compare settings (community granularity, force-layout spread, node-size range). One panel per view; skip it for results with no meaningful knob.

- **Run first.** List in `tools` the calls that produced the current view, in order (e.g. `analysis_louvain_communities`, `visualization_set_node_color`). They may have run in an earlier turn; their latest arguments are reused.
- **Fields**: 1–4, most influential first. Pair parameters that act together (ForceAtlas2 `scaling_ratio` + `gravity`; `min_size` + `max_size`).
- **Ranges** should cover what is worth exploring on this data, not the whole mathematical domain, and must include the current value.
- **low_label / high_label**: what each end does to the view, in the conversation language.
- **Suggested value**: choose one from `[Current Network Context]` (node count, density, weights) and the result you just saw, with a one-sentence `rationale`. It is shown, not applied. If you are confident it is better, run the tool with it before offering the panel instead. Omit it when you have no data-grounded reason, unless the tool ran with an automatic default (then pass the effective value it reported).
- **In your text**: say what the fields change, and that the user can simply tell you how to adjust it.

## Reference Ranges

Starting points; narrow or shift them from the data.

| Tool.argument | Range / step | Low → high |
|---|---|---|
| `analysis_louvain_communities.resolution` | 0.2–3.0 / 0.1 | larger groups → finer groups |
| `analysis_greedy_modularity_communities.resolution` | 0.2–3.0 / 0.1 | larger groups → finer groups |
| `analysis_greedy_modularity_communities.best_n` | 2–(node count) / 1 | fewer groups → more groups |
| `visualization_set_node_size.min_size` / `max_size` | 1–200 / 1 (area, not radius) | subtle → strong size contrast |
| `analysis_pagerank.damping_factor` | 0.50–0.95 / 0.05 | local → global importance |

Layout parameters are not in this table: take their ranges from the `knobs` that `layout_suggest_parameters` returns, and a suggested value from its best candidate (see `layout`). Layout `scale` and `center` are visually inert (coordinates are renormalized); never offer them.
