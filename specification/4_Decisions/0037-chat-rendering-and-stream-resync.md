# 0037. 返答の表示を整え、取りこぼしたターンを保存値から回復する

- **状態**: 採用
- **日付**: 2026-10-23

## 背景

チャット欄に三つの問題があった。

1. モデルが書いた数式（`$\rightarrow$`）と生 HTML（色見本の `<span style="background-color:…">`）が、
   ソースのまま表示されていた。
2. 失敗したターンの返答が `I encountered an error: ClientError: 404 … {'error': {…}}` という
   例外の repr のまま保存され、本文として表示されていた。
3. 画面を離れていると返答が届かず、再読み込みすると現れた。EventSource は 10 回続けて失敗すると
   再接続をやめる。また切断中に送られたイベントは失われ、再接続しても取り直す処理がなかった。

## 決定

- **数式は描画する。** `remark-math` と `rehype-katex` で `$…$` / `$$…$$` を KaTeX で表示する。
- **生 HTML は描画しない。** 例外は色見本だけである。`background-color` に hex を持つ `<span>` は、
  既存の色チップに置き換える（`remarkColorPreview`）。システムプロンプトでも、HTML を書かず、
  色はバッククォートで囲んだ hex で書くよう指示する。
- **失敗したターンは `:::error{title="…"}` directive として保存する。** タイトルは例外の型と
  HTTP コード・状態、最初の段落はプロバイダーが返した読める説明、続く fenced block は例外の
  repr 全体である。フロントエンドはこれをエラーカードとして描き、repr は「Details」に畳む。
  旧形式の `I encountered an error:` も同じカードとして読む。
- **取りこぼしは保存されたメッセージから回復する。** 接続が切れたあとに開き直したとき、
  タブが前面に戻ったとき、ネットワークが復帰したときに、閉じた接続を張り直し、
  メッセージを取り直す。保存済みの最後のメッセージがユーザーのものでなければ、
  そのターンは終わっているので `endTurn()` する。

## 根拠

- 生 HTML をサニタイズして描画する案は却下した。依存と許可リストの保守が増える一方で、
  実際に出てくる HTML は色見本だけであり、それは既存の色チップで表せる。
- 数式を禁じるプロンプト案も却下した。KaTeX で描画できれば矢印などの記法はそのまま読める。
- SSE にイベント ID を振って `Last-Event-ID` で再送する案は却下した。ブロードキャスタに
  ターンをまたぐ履歴を持たせる必要がある。保存されたメッセージがすでに唯一の正であり、
  再読み込みと同じ経路で回復するほうが単純で、再読み込みで直るという症状とも一致する。

## 帰結

- 終端イベント以外でターンが終わる経路が一つ増える。保存された返答を再同期で見つけた場合である
  （仕様 2.3.3）。進行中のターン（最後の保存メッセージがユーザーのもの）には触れない。
- `:::error` は `markup.py` と `parseMessageContent.js` の契約に加わる（仕様 2.5.2）。
- 実装: `frontend/src/components/chat/Markdown.jsx`、`frontend/src/utils/remarkColorPreview.js`、
  `backend/app/services/llm/service.py`（`_error_reply`）、`backend/app/services/llm/markup.py`
  （`error_block`）、`frontend/src/hooks/useNetworkRealtime.js`（`onResync`）、
  `frontend/src/stores/chatStore.js`（`resyncMessages`）。
