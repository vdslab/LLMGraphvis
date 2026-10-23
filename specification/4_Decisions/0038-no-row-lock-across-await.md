# 0038. 行ロックは await をまたがず、イベントループ上で待たない

- **状態**: 採用
- **日付**: 2026-10-23
- **関連**: [0014](./0014-activation-survives-a-question.md)、[0016](./0016-parameter-tuning.md)

## 背景

2026-10-23、パラメーター調整中にバックエンド全体が応答しなくなった。`/health` も
返らず、CPU は 0% だった。`pg_stat_activity` と `pg_locks` で状態を確認したところ、
次の 2 つが互いを待っていた。

- `POST /chat/{id}/tunings/{tid}/apply` は、`chats` と `parameter_tunings` の行を
  `FOR UPDATE` でロックしたまま、パイプライン（`layout_forceatlas2` の MCP 呼び出し）を
  await していた。この接続は `idle in transaction` のまま残っていた。
- 同じチャットへの `POST /chat/{id}/process` は `async def` だった。その中で、同期の
  psycopg2 による `SELECT ... FOR UPDATE` が行ロックを待っていた。

DB セッションは同期の SQLAlchemy で、uvicorn のワーカーは 1 つである。そのため、
ロックを待つ同期呼び出しがイベントループのスレッドそのものを止める。ロックを持つ
coroutine は MCP の応答を受け取って再開できず、commit してロックを解放する機会が
来ない。結果として、プロセス全体が永久に止まった。

## 決定

1. **行ロックは await をまたがない。** ロックを取ったトランザクションは、次の
   await より前に commit か rollback で終える。エラーで戻る経路も同じである。
2. **ロックを待つ可能性のある処理は、イベントループ上で実行しない。** await を
   含まないエンドポイントは `def` にし、FastAPI の threadpool で動かす。
   `process_message` がこれに当たる。
3. **パネル単位の直列化は、DB ロックではなくプロセス内の `asyncio.Lock` で行う。**
   `tuning.apply` は 3 段に分かれる。
   - 短いトランザクションで行をロックし、検証して commit する。
   - トランザクションを持たずにパイプラインを await する。
   - もう一度短いトランザクションで行をロックし、まだ active であることを確かめて
     から記録する。

   パイプラインの実行中に確定（confirm）されたパネルは上書きせず、
   `TuningInactive`（HTTP 409）を返す。
4. **行ロックはすべて `database.for_update()` を通して取る。** Postgres では
   `lock_timeout` を設定する。規則 1 と 2 が守られていればロック待ちは短いはずで、
   長く待つのは規則が破られたときである。その場合は凍結させずに失敗させ、HTTP では
   409 を返す。エージェントのターンの中であれば、ツールの失敗として扱う。
5. **SSE の `/stream` は、所有権を確認したら DB セッションを閉じる。** ストリームが
   続く間、セッションを `idle in transaction` のまま保持しない。

## 根拠

- **DB アクセス全体を非同期ドライバ（asyncpg と AsyncSession）へ移す案**は却下した。
  エンジン、フック、ローカルツールのすべてが同期セッションを前提にしており、
  変更範囲が大きい。さらに、非同期ドライバに移っても、ロックを持ったまま
  長い await に入れば他のリクエストが長く待たされる。問題の本質はドライバではなく、
  ロックを保持する期間にある。
- **ロック取得部分だけを `run_in_threadpool` に逃がし、ロックを持ったまま MCP を
  await する案**も却下した。ループは止まらなくなる。しかし、`/process` は数分
  単位でワーカースレッドを占有し、ユーザーのメッセージ送信は layout が終わるまで
  返らない。
- **`lock_timeout` だけで済ませる案**は採らなかった。凍結を数秒に短縮できるだけで、
  その間ループは止まる。そのため、規則が破られたときの保険としてだけ使う。

## 帰結

- 不変条件として、行ロックを取ったセッションは次の await の前に commit か rollback
  する。同期の DB 呼び出しのうちロックを待ちうるものは、イベントループ上で実行しない。
- `tuning.apply` は内部で 2 回 commit する。呼び出し側のセッションで未 commit だった
  変更は、そのときに一緒に commit される。
- ワーカープロセスを増やすと、`asyncio.Lock` によるパネル単位の直列化は効かなくなる。
  その場合でも記録の段で行を再ロックして状態を確かめるため、確定済みのパネルを
  上書きすることはない。ただし、同じパネルへの適用が同時に 2 つ走ると、後に記録した
  ほうが勝つ。
- 実装の場所は次のとおりである。
  - `backend/app/core/database.py`（`for_update`、`is_lock_timeout`）
  - `backend/app/services/llm/tuning.py`（`apply`、`_lock_active`、`_plan`、
    `_run_pipeline`、`_record`）
  - `backend/app/api/v1/endpoints/chat.py`（`process_message`、`apply_parameter_tuning`、
    `stream`）
  - `backend/app/main.py`（ロックのタイムアウトを 409 に変換するハンドラ）
- 再現テストは `backend/tests/test_row_lock_deadlock.py` にある。実行には
  `TEST_POSTGRES_URL` が必要で、修正前のコードではこのテストが凍結する。
