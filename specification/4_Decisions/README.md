# 設計判断の記録 (ADR)

新機能・アーキテクチャ変更の**実装前**に、`0000-template.md` をコピーして
`NNNN-<英小文字ケバブケースの短い名前>.md` を作成します。

番号は連番。既存の実装を遡って ADR 化する必要はありません。

| # | 決定 | 状態 |
|---|---|---|
| [0001](./0001-documentation-scope.md) | 仕様書のスコープをコードから導出できないものに限定する | 採用 |
| [0002](./0002-bundled-sample-networks.md) | サンプルネットワークをGraphMLとして同梱する | 採用 |
| [0003](./0003-explicit-analysis-tools.md) | 分析操作とパラメーターを明示的な契約にする | 採用 |
| [0004](./0004-conversation-inputs.md) | チャットの質問と回答を構造化して保存する | 採用 |
| [0005](./0005-graph-direction.md) | グラフの方向性を分析まで保持する | 採用 |
| [0006](./0006-choice-ui-and-other.md) | 分析候補を選択UIと自由入力で提示する | 採用 |
| [0007](./0007-gemini-3-model-contract.md) | Gemini 3 の推論・ツール呼び出し契約に追従する | 採用 |
| [0008](./0008-d3-categorical-palettes.md) | カテゴリ色に D3 の名前付きパレットを採用する | 採用 |
| [0009](./0009-structured-chat-markup-and-tool-observations.md) | チャット構造を Markdown directive と軽量な観測結果に分離する | 採用 |
| [0010](./0010-progressive-tool-disclosure.md) | ツール定義をターン内で段階的に公開する | 採用（[0014](./0014-activation-survives-a-question.md) が「状態はターン間で共有しない」を一点だけ改めた） |
| [0011](./0011-conversation-language.md) | 内部言語と会話言語の分離 | 採用 |
| [0012](./0012-data-grounded-analysis-planning.md) | 元データの意味から分析を提案する | 採用 |
| [0013](./0013-composite-encoding-and-conversation.md) | 視覚チャネルを合成して提案し、会話で進める | 採用 |
| [0014](./0014-activation-survives-a-question.md) | ツール公開状態は ask_user の回答をまたいで引き継ぐ | 採用 |
| [0015](./0015-allow-consecutive-choice-ui.md) | 回答再開ターンでの分析後の選択肢提示を許可する | 採用 |
| [0016](./0016-parameter-tuning.md) | パラメーター調整は言葉を主とし、上級者向けパネルと状態を共有する | 採用 |
| [0017](./0017-layout-quality-metrics.md) | レイアウトは描画結果を数値で評価し、パラメーターの数値はコードだけが持つ | 採用 |
| [0018](./0018-layout-tuning-choice.md) | レイアウトを描いた直後に、調整の進め方を3択で尋ねる | 採用 |
| [0019](./0019-layout-readability-in-the-canvas.md) | 描画した配置の読みやすさをキャンバスから確認できるようにする | 採用 |
| [0020](./0020-conversation-and-interaction-tabs.md) | 会話と操作 UI をチャット欄の中で切り替える | 採用 |
| [0021](./0021-analysis-operation-feedback.md) | 分析操作ごとの分かりにくさを記録し、次の会話に反映する | 廃止（[0022](./0022-evaluator-friction-journal.md) に置き換え） |
| [0022](./0022-evaluator-friction-journal.md) | 評価役AIが分析操作の分かりにくさを記録する | 採用 |
| [0023](./0023-view-navigation-and-labels.md) | 表示範囲・強調・ラベルをエージェントが操作できるチャネルにする | 採用 |
| [0024](./0024-bounded-tool-observations.md) | ツール結果の大きさをネットワークの規模から切り離す | 採用 |
| [0025](./0025-normalized-token-usage.md) | トークン使用量をプロバイダー共通の意味で記録する | 採用 |
| [0026](./0026-user-settings.md) | ユーザー設定: 既定モデルとパスワード変更 | 採用 |
| [0027](./0027-skills-are-the-only-procedures.md) | 手順は Skill だけに置き、すべてのツールを Skill から到達可能にする | 採用 |
| [0028](./0028-view-versions.md) | 表示を版として記録し、会話の任意の時点の表示に戻せるようにする | 提案 |
| [0029](./0029-numeric-mapping-transform-and-edge-style.md) | 数値の対応付けに変換と範囲を与え、エッジを一様に調整できるようにする | 採用 |
| [0030](./0030-attribute-role-and-measurement.md) | 属性に役割と尺度を持たせ、エンコーディングをそこから選ぶ | 採用 |
| [0031](./0031-generated-schema-diagram.md) | 列レベルの ER 図はモデルから生成し、仕様書には意図の図だけを描く | 採用 |
| [0032](./0032-agent-turn-trace.md) | エージェントのターンを構造化トレースとして記録する | 採用 |
