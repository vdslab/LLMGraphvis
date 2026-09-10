# 0007. Gemini 3 の推論・ツール呼び出し契約に追従する

- **状態**: 採用
- **日付**: 2026-09-11

## 背景

Gemini の選択肢と既定値が 2.5 系に固定され、最新の安定版を選べない。
さらに Gemini 3 系は推論量を数値ではなくレベルで指定し、複数ターンの
ツール呼び出しでは呼び出し ID と thought signature の保持を前提とする。
モデル名だけを更新すると、ツール実行後の再生成で履歴が不正になる。

## 決定

最新の安定版 Flash を Google プロバイダの既定モデルとする。Gemini 3 系には
`thinking_level` を使い、2.5 系の既存設定とはモデル世代で切り替える。
GenerateContent API を使う間は、function call の ID と thought signature を
プロバイダ非依存の履歴に保持し、対応する function response に同じ ID を返す。

永続化済み履歴にも ID と signature を保存する。更新前の履歴など signature が
ないツール往復は Gemini 3 への送信時だけ除外し、最終応答テキストは残す。

## 根拠

既存の ReAct ループは各イテレーションの全履歴を明示的に組み立てるため、
状態をサーバー側に持つ Interactions API への全面移行よりも、現在の
GenerateContent API 契約を正しく満たす変更の方が影響範囲が小さい。

常に変化する `latest` エイリアスは、予告後にモデル挙動が入れ替わる。
再現可能な実験と会話単位のモデル固定を優先し、具体的な安定版 ID を使う。

## 帰結

Gemini 3 のツール呼び出し情報は `providers/types.py`、Google SDK との変換は
`providers/google_genai.py`、ターンをまたぐ保存は `ToolExecution` が担う。
モデル更新時はカタログ、既定値、料金表、環境変数例を同時に更新する。
プレビュー版は明示的な選択肢として扱い、既定モデルにはしない。
Vertex AI の既定ロケーションは、Gemini 3.8 が提供される `global` とする。
