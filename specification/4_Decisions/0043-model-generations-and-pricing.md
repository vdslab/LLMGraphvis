# 0043. モデルの世代差はアダプターで吸収し、単価は期間と入力長で引く

- **状態**: 採用
- **日付**: 2026-10-27

## 背景

2026 年 10 月時点で、選択肢・既定値・単価表・SDK が実際の提供状況とずれていた。

- **単価表の誤り。** `claude-sonnet-5` は $3/$15 で登録されていたが実際は $2/$10、
  `gemini-2.5-pro`・`gemini-2.5-flash` のキャッシュ単価も公表値と異なっていた。
  GPT-5.6 系は値下げ後の価格に追従していなかった。
- **入力長と日付で単価が変わる。** Gemini Pro 系は 200k、Claude Haiku 5.5 は 100k、
  GPT-5.6 以降は 272k を超えるプロンプトで高い単価になる。Gemini 4 Argon（2026-12-01）
  と Gemini 3.8 Flash ほか（2027-01-01）は値上げが予告されている。単価表は 1 モデル
  1 行で、どちらも表せなかった。
- **Claude の推論設定が全モデル共通だった。** 全モデルに `thinking: adaptive` を送って
  いたが、Claude Haiku 4.5 は adaptive に対応せず、トークン予算で指定する。また
  Claude Opus 4.7 以降は思考の表示が既定で省略（`display: "omitted"`）になり、
  思考ストリームが空のまま流れて UI に何も出ていなかった。
- **拒否が空応答に見えた。** Claude が安全上の理由で応答を止めると
  `stop_reason: "refusal"` が返るが、アダプターは無視しており、ターンは何も言わずに
  終わっていた。
- **Gemini の判定がモデル名の接頭辞 `gemini-3` だった。** `gemini-4-argon` は思考
  レベルも thought signature の扱いも受けず、`*-thinking-exp` 用の数値予算の経路は
  対象モデルの提供終了後も残っていた。
- **SDK が古い。** `anthropic` 2.0 は API バージョン 2026-10-21 を既定で送る。

## 決定

1. **モデル世代の差は各プロバイダーのアダプターに閉じ込める。** エンジンと
   プロンプトはモデル名で分岐しない。
   - Claude: Haiku 4.5 とそれ以前は `{"type": "enabled", "budget_tokens": N}`、
     それ以外は `{"type": "adaptive", "display": "summarized"}` を送る。推論量は
     任意の `ANTHROPIC_EFFORT`（`output_config.effort`）で指定し、未指定なら
     モデルの既定に任せる。
   - Claude: `stop_reason: "refusal"` は例外として送出し、エラーとしてターンを終える。
   - Gemini: 2.5 系以外（3 系・4 系）を「思考レベルと thought signature を使う世代」
     とし、`thinking_level` と `include_thoughts` を送る。2.5 系は
     `include_thoughts` だけを送り、推論量はモデルの動的既定に任せる。
     全 Gemini モデルがネイティブの思考ストリームを持つ。
2. **既定モデル。** Claude は `claude-opus-5-5`。Gemini は ADR
   [0007](./0007-gemini-3-model-contract.md) のとおり最新の安定版 Flash
   （`gemini-3.8-flash`）のまま。OpenAI は `gpt-5.6-sol` のまま。既存の選択肢は
   会話に固定されているため削除しない。
3. **単価は「いつの、どの長さのプロンプトか」で引く。** 単価表の 1 モデルは期間ごとの
   単価を持ち、各期間は長文脈の境界と単価を持てる。コストは generate() 呼び出し
   ごとに、その呼び出しの入力トークン数で段階を選んで計算し、合計する。日付は
   記録時点（UTC）を使う。
4. **カタログに載るモデルは必ず単価を持つ。** テストで保証する。
5. SDK は `anthropic` 2.x、`google-genai` 2.x の最新に上げ、要件ファイルで
   メジャーバージョンを固定する。

## 根拠

モデル名による分岐をエンジンに持ち込むと、モデルが増えるたびに無関係な箇所が
変わる。プロバイダー API の違いを吸収するのはアダプターの責務である（ADR 0025 と
同じ考え方）。

Claude の推論の扱いは、トークン予算方式を全モデルに送る案も検討したが、Claude 4.7
以降は予算方式を 400 で拒否する。逆に adaptive を全モデルに送ると Haiku 4.5 が動か
ない。世代判定はモデル ID の集合で持ち、接頭辞の比較は避けた。

拒否は、空応答のまま終えるとユーザーには不具合と区別できない。サーバー側の
フォールバック（別モデルでの再実行）は Vertex AI で使えず、会話をモデル単位で固定
する方針（[1_Backend.md](../2_Technical_Details/1_Backend.md) 1.4.2）とも合わない
ため採らない。

入力長の段階は、ターン全体の合計で判定すると、ReAct の反復が多いだけで長文脈単価
になってしまう。課金は 1 リクエストごとなので、呼び出し単位で判定する。値上げを
コメントで残すだけの案は、施行日以降の記録を誤った値で保存し続けるため採らない。

Gemini の Interactions API への移行は ADR 0007 の判断を維持する。

## 帰結

- 世代判定は `providers/anthropic_provider.py` の `_uses_budget_thinking` と
  `providers/google_genai.py` の `_uses_thinking_level` にある。新しいモデルは
  原則として新しい世代とみなされ、古い世代だけを列挙する。
- 単価は `pricing.py` の `MODEL_PRICING`（期間と長文脈）にある。モデルを追加するとき
  は `catalog.py`・`providers/defaults.py`・`pricing.py`・`.env.sample` を同時に
  更新する。値上げが予告されたら、施行日つきの期間を追加する。
- 保存済みの `llm_usages.estimated_cost_usd` は再計算しない（ADR 0025 と同じ）。
- `GEMINI_THINKING_BUDGET` は廃止した。
- Claude の思考ブロックを次のリクエストへ返す（preserved thinking）ことは扱わない。
  保存形式の変更を伴うため、別の決定とする。
