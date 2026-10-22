---
name: error-recovery
description: Diagnosing tool failures and policy refusals, and knowing when to stop retrying and report to the user. Load this after a tool returns an error or a blocked_by field.
triggers: [error, エラー, 失敗, failed, not found, 見つから, 存在しない, blocked, ブロック, 拒否, invalid, 無効, retry, 再試行, やり直]
related_tools: [node_search, network_list_node_attributes, network_list_edge_attributes, visualization_get_state]
---

## Error Classification

- **Policy Refusal (`blocked_by` present)**: Pre-execution check rejected the call. Retrying identical arguments will be refused again. Read the `error` message and apply the prescribed remedy:
  - *Attribute missing*: Pick from the real attribute names listed in the message, or ask user.
  - *Computation too expensive*: Use approximation (e.g. `k` for betweenness) or extract a subgraph.
  - *Repeated identical call*: Use the already-obtained result.
- **Tool Error (`error` present without `blocked_by`)**: Execution attempted and failed:
  - *Node not found*: Resolve label to ID using `node_search(query=...)`, then retry with ID.
  - *Attribute not found*: Re-check return message of computing tool or list attributes.
  - *Invalid parameter*: Check schema bounds. Ask user if changing value alters analysis intent.
  - *Layout failure*: Fall back to ForceAtlas2/Spring if graph is non-planar or unpartitioned.
  - *Empty filter*: Not a fatal error; suggest a looser filter condition.

## Recovery Rules

1. **One Targeted Fix**: Make at most one corrective attempt addressing the specific failure reason. If the tool needed for correction is unexposed, use `tool_search`.
2. **Stop and Consult**: If correction fails, stop immediately. Report what was attempted, quote the error, and ask the user for clarification. (3 failures of the same tool aborts the turn automatically).
3. **Honest Reporting**: State clearly what failed and what fallback or partial result was obtained. Never report a fallback as if it were the requested operation.
