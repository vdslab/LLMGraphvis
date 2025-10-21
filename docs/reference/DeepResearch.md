**  

# LLM駆動型インタラクティブグラフ分析プラットフォームのアーキテクチャ設計

  
<br/>

## 第1章: コアバックエンドアーキテクチャ：パフォーマンスとスケーラビリティ

  

本章では、システムの根幹をなすバックエンド技術の基盤を確立します。ここでの技術選定は、計算負荷の高いグラフ分析の処理、リアルタイムのユーザーインタラクション管理、そしてスケーラブルなAPIの提供という、システムの核心的要件によって決定されます。

  

### 1.1. フレームワーク選定：FastAPIが最適な選択肢である理由

  

本プロジェクトのバックエンドフレームワークとして、DjangoではなくFastAPIを推奨します。Djangoは堅牢で「全部入り」のフレームワークであり、包括的なWebアプリケーションには非常に優れています 1。しかし、その同期的な性質とAPI機能におけるDjango REST Framework (DRF) への依存は、本プロジェクトのような高いパフォーマンスが求められるAPI中心のリアルタイムユースケースには最適とは言えません。

このアプリケーションの要件は、単一の技術選定が他の技術選定に影響を与える、相互に関連したものです。インタラクティブな体験を提供するにはリアルタイム更新が不可欠であり、これはWebSocketによって最も効果的に実現されます。WebSocketは永続的なI/Oバウンド接続であり、FastAPIのような非同期ネイティブなフレームワークは、同期的フレームワークよりも効率的にこれらの接続を処理できます。同時に、複雑なグラフ分析は計算に時間がかかり、HTTPリクエストをブロックしてしまうため、バックグラウンドでのタスク実行（Celery）が必要となります。これらのタスクキューもまたI/Oバウンドであり、非同期コンテキストで効率的に管理できます。したがって、アプリケーションの核心的な要件が、必然的に非同期ファーストのフレームワークであるFastAPIの採用へと導きます。

FastAPIはStarletteとPydanticを基盤として構築されており、ネイティブな非同期機能によって卓越したパフォーマンスを提供します 1。これは単なる「あれば良い」機能ではなく、決定的なアーキテクチャ上の利点です。本アプリケーションは、HTTPリクエストの処理、リアルタイム更新のための永続的なWebSocket接続の管理、そして長時間実行タスクのメッセージキューへのディスパッチを同時に行わなければなりません。FastAPIのasync/await構文により、これらのI/Oバウンドな操作を単一のイベントループ内で効率的に並行処理でき、従来型の同期フレームワークと比較してスループットとリソース使用率を劇的に向上させます。

システムの性質上、これは専門的なフロントエンドにサービスを提供するAPIが中心となります。FastAPIはこの領域で非常に優れており、インタラクティブなAPIドキュメント（Swagger UIおよびReDoc）を標準で自動生成するため、開発とテストが加速されます 2。対照的に、Djangoで同等のRESTful機能を実現するには、DRFの追加と設定が必要です 2。さらに、FastAPIとPydanticの統合は厳密な型ヒントを強制し、これにより自己文書化され、エディタサポートに優れた堅牢なコードが実現され、実行時エラーが削減されます。これは、複雑なデータ処理を行うバックエンドにとって極めて重要な特徴です 1。

  

### 1.2. ノンブロッキングなグラフ計算のための非同期タスク処理

  

中心性指標（次数、媒介、固有ベクトルなど）の計算、コミュニティ検出の実行、あるいは力学的配置アルゴリズムの計算といったグラフアルゴリズムは、特に大規模なグラフにおいて計算コストが高く、実行時間が不確定になる可能性があります。これらのタスクをHTTPリクエスト・レスポンスサイクル内で実行すると、サーバーのワーカープロセスがブロックされ、リクエストのタイムアウトやUIの無応答を引き起こします。これはインタラクティブなアプリケーションにとって許容できるものではありません。

この問題を解決するため、メッセージブローカーとしてRabbitMQを用いたタスクキューCeleryを実装します。このアーキテクチャは、APIエンドポイント（タスクの生産者）と計算プロセス（タスクの消費者またはワーカー）を分離します 4。この分離の主目的は、単に長時間タスクを処理することだけではなく、ユーザーのインタラクションループと計算ループを根本的に切り離すことにあります。これにより、システムは即座にフィードバック（例：「計算を開始しました。タスクIDはXです」）を返し、UIの応答性を維持できます。これは、基盤となる計算にかなりの時間がかかる場合でも、高いパフォーマンスをユーザーに体感させるための、データ集約型インタラクティブアプリケーション設計における重要な原則です。

実装フローは以下の通りです。

1. FastAPIエンドポイントがリクエスト（例：「媒介中心性を計算して」）を受信します。
    
2. グラフ識別子と必要なパラメータを渡し、RabbitMQを介してCeleryキューにタスクを即座にディスパッチします。この処理にはdelay()メソッドが使用されます 6。
    
3. エンドポイントはクライアントにtask_idを即座に返し、HTTPワーカーを解放します。
    
4. APIサーバーとは独立して実行されている1つ以上のCeleryワーカープロセスが、キューからタスクを取得します。
    
5. ワーカーはグラフデータをロードし、NetworkXによる計算を実行し、結果を永続化層（第2章で詳述）に保存します。
    
6. クライアントはtask_idを使用してステータスエンドポイントをポーリングし完了を確認するか、より望ましい方法として、バックエンドがタスク完了時にWebSocketを介して通知をプッシュします（第4章で詳述）。
    

代替案として、純粋な非同期ネイティブスタックには、Celeryの代替としてTaskiq 8 があります。これはFastAPIの依存性注入システムとのより良い統合と、ネイティブなasync関数のサポートを提供します。本プロジェクトでは、本番環境での成熟度と実証済みの信頼性からCeleryを推奨しますが、Taskiqは将来のプロジェクトで注目すべき技術です。

  

## 第2章: グラフ中心アプリケーションのためのハイブリッドデータ永続化戦略

  

本章では、仕様書で要求されている「NetworkXに最適化された」データベース設計と、計算結果の永続化について詳述します。本アプリケーションの多様なデータ保存およびアクセスパターンを満たすためには、単一のデータベース技術では不十分です。そのため、ハイブリッドな、いわゆるポリグロット永続化戦略を提案します。

  

### 2.1. 中核的課題：NetworkXオブジェクトの永続化

  

NetworkXのグラフはメモリ上のPythonオブジェクトであり 9、直接的な永続化を目的として設計されていません。pickleやJSON形式（node_link_dataなど）を用いてファイルにシリアライズすることは可能ですが、これはスケーラブルなデータベースソリューションではありません 9。大規模なグラフを単一のBLOBとしてリレーショナルデータベースに保存することは、クエリや部分的な更新において極めて非効率です。

このアーキテクチャでは、NetworkXの役割を正しく再定義します。NetworkXは強力ですが、永続的なストレージツールではなく、あくまで一時的なメモリ内計算エンジンです。データベースの役割は、このエンジンにデータを供給し、その出力を保存することです。この考え方を明確にすることで、NetworkXオブジェクト全体をBLOBとして保存しようとするようなアーキテクチャ上の誤りを防ぐことができます。

  

### 2.2. プライマリグラフストレージ：ネイティブグラフデータベース（Neo4j）

  

グラフのトポロジー（ノード、エッジ、およびそれらの内在的プロパティ）の「信頼できる唯一の情報源（Source of Truth）」は、Neo4jのようなネイティブグラフデータベースであるべきです。グラフデータベースはNetworkXモデルを反映した方法でデータを保存するため、グラフ構造の保存とクエリに最も自然でパフォーマンスの高い選択肢となります 9。

グラフデータベースの主な利点は、Cypher（Neo4jの場合）のような宣言的なクエリ言語を使用して、グラフ構造に対して強力なクエリを実行できることです。これにより、複数ホップのトラバーサル、パス検索、パターンマッチングといった操作をデータベース層で直接実行できます。これらのタスクは、リレーショナルデータベース上でSQLを使用して実行する場合、非常に非効率的または複雑になります。

ワークフローは以下のようになります。

1. ユーザーがグラフデータ（例：CSV）をアップロードします。
    
2. バックエンドはこのデータを解析し、Neo4jに投入してノードとリレーションシップを作成します。
    
3. ユーザーが分析セッションを開始すると、バックエンドはNeo4jにクエリを発行して関連するサブグラフを取得します。
    
4. クエリ結果は、アルゴリズム分析のためにメモリ上のNetworkX Graphオブジェクトを構築するために使用されます 12。これにより、永続的ストレージと構造的クエリ（Neo4j）の関心事と、メモリ内でのアルゴリズム計算（NetworkX）の関心事が分離されます。
    

  

### 2.3. 高速キャッシュ層：計算済みメトリクスと状態のためのRedis

  

仕様書では、一度計算したメトリクス（中心性スコアなど）やレイアウト座標は再計算を避けるために永続化することが求められています。これらの結果はグラフの本来のトポロジーの一部ではなく、派生データです。これらをノードプロパティとしてNeo4jに書き戻すことも可能ですが、プライマリグラフモデルを煩雑にする可能性があります。より効果的なパターンは、Redisのような高速なインメモリキーバリューストアをキャッシュ層として使用することです。

Redisは、「グラフデータ」が単一のものではないという理解に基づき採用されます。グラフデータは、(1) 基本的なトポロジー、(2) 派生した分析結果、(3) アプリケーションのメタデータ、という3つの異なるカテゴリに分解できます。提案するハイブリッドアーキテクチャは、この分解の直接的な結果であり、各データカテゴリを、それを扱うために特化して構築されたデータベース技術に割り当てます。

Celeryワーカーがメトリクス（例：媒介中心性）の計算を終えると、その結果をRedisに保存します。適切なキーは`project:{project_id}:graph:{graph_id}:metric:betweenness`のようになります。値は、ノードIDとそのスコアをマッピングしたシリアライズ済みの辞書です。Redisのサブミリ秒のレイテンシは、この目的に理想的であり、キャッシュされた結果の取得がほぼ瞬時に行われることを保証します 18。また、Redisは第4章で詳述するように、分散WebSocket接続状態の管理にも使用されます。

  

### 2.4. アプリケーションおよびユーザーデータ：PostgreSQL

  

ユーザーアカウント、プロジェクトのメタデータ、認証情報、保存された可視化設定など、構造化されたリレーショナルなアプリケーションデータは、PostgreSQLのような従来のリレーショナルデータベースで管理するのが最適です。データ整合性、トランザクションの一貫性（ACID）、そして成熟したツールとORMのエコシステムにおけるその強みは、この種のデータにとって業界標準となっています 18。このデータをグラフモデルやキーバリューモデルに無理に押し込むことはアンチパターンとなります。

|     |     |     |     |     |     |
| --- | --- | --- | --- | --- | --- |
| テクノロジー | プライマリデータモデル | アーキテクチャにおける役割 | 保存されるデータ | 本プロジェクトにおける主な強み | 主な弱点 |
| Neo4j | プロパティグラフ | グラフのトポロジーの永続的ストレージ | ノード、エッジ、およびそれらの内在的プロパティ | グラフ構造のネイティブな保存と、Cypherによる効率的なトラバーサルおよびパターンマッチングクエリ。 | 複雑な集計やトランザクション処理には不向き。 |
| Redis | キーバリュー | 高速キャッシュ層およびメッセージブローカー | 計算済みメトリクス、レイアウト座標、WebSocket接続状態、タスクキュー。 | サブミリ秒のレイテンシでのデータ読み書き。Pub/Sub機能によるスケーラブルな状態同期。 | インメモリのため永続性は限定的。複雑なクエリは不可能。 |
| PostgreSQL | リレーショナル | アプリケーションのプライマリデータベース | ユーザーアカウント、プロジェクトメタデータ、認証情報、保存された設定。 | ACID準拠による強力なデータ整合性とトランザクションの信頼性。成熟したエコシステム。 | グラフのような高度に接続されたデータのクエリは非効率。 |

  

## 第3章: LLM Function Callingによる自然言語制御プレーンの実装

  

本章では、ユーザーの自然言語コマンドをバックエンドでの具体的なアクションに変換し、アプリケーションの核となるインタラクティブループを形成する方法について詳述します。

  

### 3.1. メカニズム：LLM Function Calling

  

Function Callingは、LLMが外部ツールと対話することを可能にする機能です。単にテキストを生成するだけでなく、ユーザーのクエリと利用可能な関数のスキーマをプロンプトとして与えられると、LLMは呼び出すべき関数とその引数を指定した構造化JSONオブジェクトを生成できます 20。

実行フローは以下の通りです。

1. フロントエンドがユーザーの自然言語クエリ（例：「重要なノードを大きくして」）をバックエンドに送信します。
    
2. バックエンドはLLM用のプロンプトを構築します。このプロンプトには、ユーザーのクエリ、会話履歴、そして利用可能な「ツール」（関数）の定義済みリスト（説明とパラメータスキーマを含む）が含まれます。
    
3. LLMがプロンプトを処理し、JSONオブジェクト（例：`{ "name": "set_node_size_by_metric", "arguments": { "metric": "betweenness_centrality" } }`）を返します。
    
4. バックエンドはこのJSONを解析し、関数名と引数を検証した後、対応するPython関数を実行します。
    
5. 関数の実行により可視化状態が変更され、その変更はWebSocketを介してフロントエンドにプッシュされます。
    

  

### 3.2. 堅牢な関数スキーマの設計

  

Function Callingの有効性は、適切に設計された関数セットに完全に依存します。LLMが理解できるよう、関数名とパラメータの説明は明確で曖昧さがないものでなければなりません 22。

必須となる関数カテゴリは以下の通りです。

- ビジュアルマッピング: set_node_size_by_metric(metric: str), set_node_color_by_category(attribute: str), set_node_color_by_community()
    
- レイアウト制御: apply_layout(layout_name: str)（layout_nameは 'force_directed', 'circular', 'kamada_kawai' など）
    
- フィルタリングと選択: filter_nodes_by_property(property: str, value: any, operator: str), show_neighbors(node_id: str, depth: int)
    
- 分析実行: calculate_metric(metric: str)（これはCeleryタスクをトリガーします）
    

  

### 3.3. 曖昧さと複雑なタスクのための高度なプロンプトエンジニアリング

  

プロンプト、関数スキーマ、検証ロジックの集合体は、「プロンプトウェア」24 とも呼ばれる新しい形態のソフトウェアを構成します。これは非決定的であり、明確さ、堅牢性、セキュリティに焦点を当てた独自のエンジニアリング規律を必要とします。アプリケーション全体の成功は、この「プロンプトウェアエンジニアリング」の質にかかっています。

「重要な人物を表示して」のようなクエリは曖昧です。「重要性」は定義されたメトリクスではありません。単純な実装では失敗するか、メトリクスを幻覚（ハルシネーション）する可能性があります。この課題に対処するため、LLMが曖昧さに直面した際に明確化を求めるように指示する戦略が重要です。このアプローチは、LLMを単なる「自然言語コマンドライン」から「対話型分析パートナー」へと昇華させます。ユーザーが曖昧なクエリを投げかけた場合、単純なシステムは失敗するか推測に頼るため、ユーザーの不満につながります。一方、優れたシステムは曖昧さを認識し、明確化のための質問を投げかけます。これにより、ユーザーを導き、利用可能な分析オプションについて教育することで、成功裏に結果を導き、より強力で使いやすいツールとなります。

最近の研究では、LLMが曖昧さに直面した際に明確化を求める必要性が強調されています 25。システムプロンプトでは、ユーザーの要求が不正確な場合に詳細な情報を尋ねるようLLMに明示的に指示すべきです。このアプローチは「Ask-when-Needed (AwN)」25 のようなフレームワークで形式化されています。

例えば、以下のような対話が考えられます。

- ユーザー：「重要な人物を表示して。」
    
- LLM（特別なclarify関数呼び出しを介して）：「重要性を判断するために、どの指標を使用しますか？選択肢は 'degree' (接続数), 'betweenness' (ブリッジとしての役割), 'pagerank' (影響力) です。」
    

「コミュニティを見つけ、最大のコミュニティで最も中心的なノードを強調表示して」のような複雑なリクエストに対しては、LLMが複数の関数呼び出しを連鎖させる必要があるかもしれません。プロンプトは、ステップバイステップの思考プロセス（Chain-of-Thought）を促すべきです 22。バックエンドは、LLMからの一連の関数呼び出しを順次実行できるように設計する必要があります。

  

### 3.4. セキュリティの必須要件：LLMは信頼できない入力ベクトル

  

LLMによって生成されたJSONは、信頼できないユーザー入力として扱わなければなりません。これは、インジェクション攻撃や意図しない操作の潜在的なベクトルです。LLMが提案した関数呼び出しを実行する前に、バックエンドは厳格な検証を行う必要があります 21。

1. 関数ホワイトリスト: 関数名が実行許可された関数のリストに含まれているか。
    
2. パラメータ検証: 引数が期待される型や制約（例：metricパラメータが有効な計算済みメトリクスの一つであるか）に一致しているか。堅牢な検証のためにPydanticモデルを使用します。
    
3. サニタイズ: インジェクション攻撃を防ぐために、すべての文字列入力をサニタイズします。
    

機密性の高い操作や、基盤となるデータベースを直接変更する可能性のある関数を、LLMのFunction Calling機能を通じて決して公開してはなりません。

  

## 第4章: 高性能でインタラクティブなフロントエンドの設計

  

本章では、バックエンド中心のアーキテクチャ方針に沿って、流動的で応答性が高く、スケーラブルな可視化体験を提供するために必要なクライアントサイドの技術とパターンに焦点を当てます。

  

### 4.1. 可視化ライブラリの選定：パフォーマンスとカスタマイズ性のトレードオフ

  

フロントエンドにおける主要な決定は、グラフ可視化ライブラリの選択です。この選択は、大規模グラフでのパフォーマンスに最適化されたWebGLベースのエンジンと、最大限の柔軟性を提供するSVG/Canvasベースのライブラリとの間のトレードオフになります。

大規模でインタラクティブなネットワークをレンダリングするためには、Sigma.jsを推奨します。これはWebGLを使用し、レンダリングをGPUにオフロードすることで、数千から数万のノードとエッジを描画しながらもインタラクティビティを維持できます 28。

一方、D3.jsはレンダリングに対する比類なき制御を提供し、完全にカスタムな視覚表現を可能にします。しかし、そのSVGベースのアプローチは、大規模なノードリンク図のスケーラビリティには劣ります 29。D3.jsは、主要なインタラクティブグラフキャンバスではなく、小規模なサマリービューや特定のチャートタイプに限定して使用すべきです。

|     |     |     |     |     |     |
| --- | --- | --- | --- | --- | --- |
| ライブラリ | プライマリレンダリングエンジン | パフォーマンス（大規模グラフ） | カスタマイズの柔軟性 | 使いやすさ | エコシステム |
| Sigma.js | WebGL | 非常に高い | 中程度（カスタムシェーダーが必要な場合あり） | 中程度（グラフ描画に特化） | 良好（Graphologyと連携） |
| D3.js | SVG/Canvas | 低い  | 非常に高い（ほぼ無制限） | 低い（低レベルAPI） | 非常に広範 |
| Cytoscape.js | Canvas | 高い  | 高い  | 高い（豊富なAPI） | 広範（生物学分野で強力） |

  

### 4.2. WebSocketによるリアルタイム状態同期

  

このアーキテクチャでは、バックエンドが各ユーザーセッションの確定的な「可視化状態」を保持し、フロントエンドはこの状態の受動的なレンダラーとして機能します。WebSocketは、フロントエンドをバックエンドとリアルタイムで同期させるために必要な、永続的で双方向の通信チャネルを提供します 32。FastAPIはWebSocketを直接的かつ容易にサポートします 34。

このシステムの最も複雑な部分は、個々のコンポーネントではなく、それらの間の状態管理です。ユーザーの意図から自然言語、LLM生成の関数呼び出し、バックエンドの状態オブジェクト、WebSocketメッセージ、そしてフロントエンドのレンダリングビューへと続く状態の流れこそが、中心的なアーキテクチャ上の課題です。WebSocket、Redis Pub/Sub、JSON Patchの選択はすべて、この状態の流れをリアルタイムで、スケーラブルかつ効率的に管理する必要性から直接導き出されたものです。

単一サーバーインスタンス内のメモリ上の接続辞書では、スケーラビリティに限界があります。アプリケーションが複数のサーバーインスタンスにデプロイされた場合（スケーラビリティのための標準的な手法）、サーバーAに接続しているユーザーは、サーバーBのプロセスによってトリガーされた更新を受け取ることができません。この問題を解決するため、Redis Pub/Subをメッセージバスとして使用します。状態変更が発生すると、バックエンドサーバーはユーザー固有のRedisチャネル（例：`channel:user_id:{user_id}`）にメッセージを公開します。すべてのアプリケーションサーバーがこれらのチャネルを購読し、メッセージを受信すると、そのユーザーのWebSocket接続を保持しているかを確認し、保持していればメッセージを転送します 35。これにより、サーバーが分離され、水平スケーリングが可能になります。

さらに、わずかな変更のたびに可視化状態オブジェクト全体を送信するのは非効率です。JSON Patch（RFC 6902）標準を使用し、バックエンドで旧状態と新状態の差分（「パッチ」）を計算し、この小さなパッチのみをWebSocket経由で送信します。フロントエンドは、このパッチをローカルの状態オブジェクトに適用することで、ネットワークトラフィックとクライアントサイドの処理を最小限に抑えます 33。

  

### 4.3. オプティミスティックUIによるユーザーエクスペリエンスの向上

  

UIを瞬間的に感じさせるため、フロントエンドはバックエンドからの確認を待つ前に、ユーザーが要求した変更を即座に適用することができます。これは「オプティミスティックアップデート（楽観的更新）」と呼ばれます 36。

フローは以下の通りです。

1. ユーザーがノードの色を変更するボタンをクリックします。
    
2. フロントエンドは、ローカルのSigma.jsインスタンスでノードの色を即座に変更し、同時に変更を要求するWebSocketメッセージをバックエンドに送信します。
    
3. バックエンドはリクエストを処理し、状態を更新し、確定した変更を（JSON Patchとして）ブロードキャストします。
    
4. バックエンドからの確認がオプティミスティックアップデートと一致する場合、視覚的な変化はありません。バックエンドが変更を拒否した場合、フロントエンドはサーバーから受信した状態に色を戻します。これにより、バックエンドを信頼できる情報源として維持しつつ、UIの応答性を高めることができます。
    

スムーズでインタラクティブな体験を実現するには、スタックのすべての層で最適化が必要です。高速なバックエンド（FastAPI）も、フロントエンドのレンダリングが遅ければ（WebGL/Sigma.jsの選択が重要）意味がありません。高速なレンダリングエンジンも、ネットワークがボトルネックであれば（JSON Patchの使用が重要）無駄になります。高速なネットワークも、バックエンドが計算でブロックされていれば（Celeryの使用が重要）意味をなしません。これは、複雑なWebアプリケーションにおけるパフォーマンスの深い相互関連性を示しています。

  

## 第5章: 包括的なセキュリティとユーザー認証

  

本章では、API認証とセッション管理に関する現代的なベストプラクティスに焦点を当て、アプリケーションのための堅牢なセキュリティモデルを詳述します。

  

### 5.1. 認証フロー：JWTアクセストークンとリフレッシュトークン

  

JSON Web Tokens (JWT) を使用したトークンベースの認証を実装し、ログインにはOAuth2パスワードフローに従います 38。セキュリティとユーザーエクスペリエンスのためには、2つのトークン戦略が不可欠です。

1. アクセストークン: ユーザーの身元情報を含む、短命のJWT（例：15分有効）。保護されたリソースにアクセスするために、すべてのAPIリクエストのAuthorization: Bearer &lt;token&gt;ヘッダーで送信されます。その短い寿命により、漏洩した場合の損害を最小限に抑えます。
    
2. リフレッシュトークン: 長命で不透明なトークン（例：7日間有効）。古いアクセストークンが失効した際に、新しいアクセストークンを取得するためだけに使用されます。専用の/token/refreshエンドポイントに送信されます。
    

JWTのセキュリティは、リスクを軽減するためのトレードオフの連続です。JWTのステートレス性はスケーラビリティを提供しますが、失効の問題を生み出します。2トークン戦略は、この問題への直接的な答えです。頻繁なAPI呼び出し（アクセストークン）に対してはステートレス性の利点を維持しつつ、頻度の低いリフレッシュ操作でステートフルなチェック（失効確認）を集中化します。アクセストークンの短い寿命は、漏洩したトークンの「脆弱性の窓」を限定するためのトレードオフです。

  

### 5.2. 安全なトークンハンドリング：XSS攻撃の緩和

  

フロントエンドでトークンを扱う最も一般的な方法はlocalStorageに保存することですが、これは安全ではありません。サイト上のクロスサイトスクリプティング（XSS）脆弱性により、悪意のあるJavaScriptがトークンを盗むことが可能になるためです。

クライアント側でのトークンの保存場所は、重要なセキュリティ上の決定です。リフレッシュトークンに対するHttpOnlyクッキーのパターンは、XSS攻撃の蔓延に対する直接的な対応策です。これは、ブラウザ自体が提供するセキュリティ機能を活用すべきであり、サーバーサイド開発者はクライアントサイドの脅威を理解した上で認証フローを設計しなければならないことを示しています。

ベストプラクティスは以下の通りです。

- アクセストークンは、アプリケーションメモリ（例：JavaScript変数）に保存できます。
    
- より価値が高く長命な資格情報であるリフレッシュトークンは、安全なHttpOnlyクッキーに保存する必要があります 40。HttpOnlyクッキーはクライアントサイドのJavaScriptからアクセスできないため、XSSベースのトークン盗難に対して強力な保護を提供します。ブラウザは、このクッキーを/token/refreshエンドポイントに自動的に送信します。
    

  

### 5.3. トークン失効アーキテクチャ：JWTのステートレスな性質への対応

  

設計上、JWTは自己完結型であり、アイデンティティサーバーに問い合わせることなく暗号署名を用いて検証されます。これは、一度発行されたトークンは有効期限が切れるまで有効であることを意味し、盗まれたトークンを遠隔で「無効化」することはできません 42。

この問題の解決策として、リフレッシュトークンの失効メカニズムを実装します。すべての新しいアクセストークンは有効なリフレッシュトークンに依存するため、リフレッシュトークンを失効させることで、現在のアクセストークンの有効期限が切れた後にユーザーのセッションを効果的に無効化できます。

Redisを使用した実装は以下の通りです。

1. ユーザーがログアウトするか、管理者がセッションを失効させると、そのリフレッシュトークンの一意な識別子（jtiクレーム）がRedisセットに保存されたブラックリストに追加されます。
    
2. クライアントが/token/refreshエンドポイントでリフレッシュトークンを使用しようとすると、バックエンドはまずそのトークンのjtiがRedisのブラックリストに存在するかどうかを確認します。
    
3. リストに存在する場合、リクエストは401 Unauthorizedエラーで拒否され、ユーザーは再ログインを強制されます。
    
4. RedisのTTL（Time to Live）機能を使用して、トークンの元の有効期限が経過した後に失効したトークンIDをリストから自動的に削除し、リストが無限に増大するのを防ぐことができます 45。
    

  

## 第6章: 統合と戦略的提言

  
<br/>

### 6.1. アーキテクチャの統合

  

本報告書で推奨されたコンポーネント（FastAPI, Celery/RabbitMQ, Neo4j, Redis, PostgreSQL, WebSockets, Sigma.js, LLM）がどのように相互作用するかを高レベルの図で示し、アーキテクチャ全体を統合します。中心となる設計原則は、厳格なバックエンド/フロントエンドの分離、パフォーマンスのための非同期処理、データ最適化のためのポリグロット永続化、そしてセキュアバイデザインの認証モデルです。これらの選択がもたらす相乗効果、例えばRedisがキャッシュと分散状態管理の両方の目的を果たすことや、FastAPIの非同期性がWebSocketとタスクキューの両方の統合に利益をもたらすことなどを強調します。

  

### 6.2. 高レベル実装ロードマップ

  

1. フェーズ1: コアバックエンドとデータ層  
    FastAPI、ユーザーモデル用のPostgreSQL、およびNeo4jをセットアップします。データ投入パイプラインを実装します。
    
2. フェーズ2: 基本的な可視化  
    Sigma.jsを用いてフロントエンドを開発します。Neo4jからグラフをNetworkXにロードし、単純なRESTコールでフロントエンドに送信する基本的なAPIエンドポイントを実装します。
    
3. フェーズ3: 非同期分析  
    Celery/RabbitMQとRedisを統合します。グラフ計算ロジックをバックグラウンドタスクに移行し、結果のRedisへのキャッシュを実装します。
    
4. フェーズ4: リアルタイム同期  
    RESTベースのデータローディングをWebSocket接続に置き換えます。Redis Pub/SubとJSON Patchを使用した状態同期ロジックを実装します。
    
5. フェーズ5: LLM統合  
    Function Callingスキーマとプロンプトエンジニアリングロジックを開発します。LLMが生成したコマンドの検証層を実装します。
    
6. フェーズ6: セキュリティと本番環境対応  
    HttpOnlyクッキーとRedisベースの失効リストを含む完全なJWTアクセス/リフレッシュトークンフローを実装します。本番環境へのデプロイメントを設定します。
    

  

### 6.3. 結論

  

本報告書で提示されたアーキテクチャは、最先端のインタラクティブ分析プラットフォームを構築するための、堅牢でスケーラブル、かつ高性能な基盤を提供します。各技術の選定は、システムの特定の要件に対応するだけでなく、互いに補完し合い、全体として効率的で回復力のあるシステムを形成するように意図されています。この設計に従うことで、計算集約的なバックエンド処理と、流動的で応答性の高いユーザーエクスペリエンスを両立させることが可能となります。

#### 引用文献

1. FastAPI vs Django: Choosing The Right Python Web Framework, 10月 21, 2025にアクセス、 [<ins>https://www.aegissofttech.com/insights/fastapi-vs-django-python-framework/</ins>](https://www.aegissofttech.com/insights/fastapi-vs-django-python-framework/)
    
2. Django vs. FastAPI: A Detailed Comparison - Sunscrapers, 10月 21, 2025にアクセス、 [<ins>https://sunscrapers.com/blog/django-vs-fastapi-a-detailed-comparison/</ins>](https://sunscrapers.com/blog/django-vs-fastapi-a-detailed-comparison/)
    
3. Tutorial - User Guide - FastAPI, 10月 21, 2025にアクセス、 [<ins>https://fastapi.tiangolo.com/tutorial/</ins>](https://fastapi.tiangolo.com/tutorial/)
    
4. A Deep Dive into RabbitMQ & Python's Celery: How to Optimise ..., 10月 21, 2025にアクセス、 [<ins>https://towardsdatascience.com/deep-dive-into-rabbitmq-pythons-celery-how-to-optimise-your-queues/</ins>](https://towardsdatascience.com/deep-dive-into-rabbitmq-pythons-celery-how-to-optimise-your-queues/)
    
5. Running Celery with RabbitMQ - CloudAMQP, 10月 21, 2025にアクセス、 [<ins>https://www.cloudamqp.com/blog/how-to-run-celery-with-rabbitmq.html</ins>](https://www.cloudamqp.com/blog/how-to-run-celery-with-rabbitmq.html)
    
6. Celery - FastAPI + Celery =, 10月 21, 2025にアクセス、 [<ins>https://derlin.github.io/introduction-to-fastapi-and-celery/03-celery/</ins>](https://derlin.github.io/introduction-to-fastapi-and-celery/03-celery/)
    
7. Parallel running DAG of tasks in Python's Celery | by Pavlo Osadchyi - Medium, 10月 21, 2025にアクセス、 [<ins>https://medium.com/@pavloosadchyi/parallel-running-dag-of-tasks-in-pythons-celery-4ea73c88c915</ins>](https://medium.com/@pavloosadchyi/parallel-running-dag-of-tasks-in-pythons-celery-4ea73c88c915)
    
8. taskiq-python/taskiq: Distributed task queue with full async support - GitHub, 10月 21, 2025にアクセス、 [<ins>https://github.com/taskiq-python/taskiq</ins>](https://github.com/taskiq-python/taskiq)
    
9. Frequently asked questions | Memgraph's Guide for NetworkX library, 10月 21, 2025にアクセス、 [<ins>https://memgraph.github.io/networkx-guide/faq/</ins>](https://memgraph.github.io/networkx-guide/faq/)
    
10. node_link_graph — NetworkX 3.5 documentation, 10月 21, 2025にアクセス、 [<ins>https://networkx.org/documentation/stable/reference/readwrite/generated/networkx.readwrite.json_graph.node_link_graph.html</ins>](https://networkx.org/documentation/stable/reference/readwrite/generated/networkx.readwrite.json_graph.node_link_graph.html)
    
11. graph - NetworkX vs GraphDB: do they serve similar purposes ..., 10月 21, 2025にアクセス、 [<ins>https://stackoverflow.com/questions/55324415/networkx-vs-graphdb-do-they-serve-similar-purposes-when-to-use-one-or-the-othe</ins>](https://stackoverflow.com/questions/55324415/networkx-vs-graphdb-do-they-serve-similar-purposes-when-to-use-one-or-the-othe)
    
12. The graph object - Neo4j Graph Data Science Client, 10月 21, 2025にアクセス、 [<ins>https://neo4j.com/docs/graph-data-science-client/current/graph-object/</ins>](https://neo4j.com/docs/graph-data-science-client/current/graph-object/)
    
13. Tutorial — NetworkX 3.5 documentation, 10月 21, 2025にアクセス、 [<ins>https://networkx.org/documentation/stable/tutorial.html</ins>](https://networkx.org/documentation/stable/tutorial.html)
    
14. Build applications with Neo4j and Python - Neo4j Python Driver Manual, 10月 21, 2025にアクセス、 [<ins>https://neo4j.com/docs/python-manual/current/</ins>](https://neo4j.com/docs/python-manual/current/)
    
15. neo4j-graph-analytics/networkx-neo4j: NetworkX API for Neo4j Graph Algorithms. - GitHub, 10月 21, 2025にアクセス、 [<ins>https://github.com/neo4j-graph-analytics/networkx-neo4j</ins>](https://github.com/neo4j-graph-analytics/networkx-neo4j)
    
16. python - Constructing NetworkX graph from neo4j query result ..., 10月 21, 2025にアクセス、 [<ins>https://stackoverflow.com/questions/59289134/constructing-networkx-graph-from-neo4j-query-result</ins>](https://stackoverflow.com/questions/59289134/constructing-networkx-graph-from-neo4j-query-result)
    
17. Introduction to Property Graphs Using Python With Neo4j - Sease, 10月 21, 2025にアクセス、 [<ins>https://sease.io/2023/08/introduction-to-property-graphs-using-python-with-neo4j.html</ins>](https://sease.io/2023/08/introduction-to-property-graphs-using-python-with-neo4j.html)
    
18. Redis Vs PostgreSQL - Key Differences | Airbyte, 10月 21, 2025にアクセス、 [<ins>https://airbyte.com/data-engineering-resources/redis-vs-postgresql</ins>](https://airbyte.com/data-engineering-resources/redis-vs-postgresql)
    
19. Why Should I use Redis when I have PostgreSQL as my database for Django?, 10月 21, 2025にアクセス、 [<ins>https://stackoverflow.com/questions/14989390/why-should-i-use-redis-when-i-have-postgresql-as-my-database-for-django</ins>](https://stackoverflow.com/questions/14989390/why-should-i-use-redis-when-i-have-postgresql-as-my-database-for-django)
    
20. Alibaba Cloud Model Studio:Function calling, 10月 21, 2025にアクセス、 [<ins>https://www.alibabacloud.com/help/en/model-studio/qwen-function-calling</ins>](https://www.alibabacloud.com/help/en/model-studio/qwen-function-calling)
    
21. Function calling using LLMs - Martin Fowler, 10月 21, 2025にアクセス、 [<ins>https://martinfowler.com/articles/function-call-LLM.html</ins>](https://martinfowler.com/articles/function-call-LLM.html)
    
22. Function Calling - Hugging Face, 10月 21, 2025にアクセス、 [<ins>https://huggingface.co/docs/hugs/guides/function-calling</ins>](https://huggingface.co/docs/hugs/guides/function-calling)
    
23. Advanced LLM Function Calling and Tool Usage - Turing, 10月 21, 2025にアクセス、 [<ins>https://www.turing.com/services/llm-function-calling-tool-usage</ins>](https://www.turing.com/services/llm-function-calling-tool-usage)
    
24. Promptware Engineering: Software Engineering for LLM Prompt Development - arXiv, 10月 21, 2025にアクセス、 [<ins>https://arxiv.org/html/2503.02400v1</ins>](https://arxiv.org/html/2503.02400v1)
    
25. Learning to Ask: When LLM Agents Meet Unclear Instruction, 10月 21, 2025にアクセス、 [<ins>https://arxiv.org/pdf/2409.00557</ins>](https://arxiv.org/pdf/2409.00557)
    
26. Conversation Routines: A Prompt Engineering Framework for Task-Oriented Dialog Systems, 10月 21, 2025にアクセス、 [<ins>https://arxiv.org/html/2501.11613v2</ins>](https://arxiv.org/html/2501.11613v2)
    
27. A Survey of Prompt Engineering Methods in Large Language Models for Different NLP Tasks - arXiv, 10月 21, 2025にアクセス、 [<ins>https://arxiv.org/html/2407.12994v1</ins>](https://arxiv.org/html/2407.12994v1)
    
28. olavtenbosch/awesome-web-visualization-frameworks ... - GitHub, 10月 21, 2025にアクセス、 [<ins>https://github.com/olavtenbosch/awesome-web-visualization-frameworks</ins>](https://github.com/olavtenbosch/awesome-web-visualization-frameworks)
    
29. Sigma.js, 10月 21, 2025にアクセス、 [<ins>https://www.sigmajs.org/</ins>](https://www.sigmajs.org/)
    
30. D3.js or Sigmajs is more good for network visualisation? - Stack Overflow, 10月 21, 2025にアクセス、 [<ins>https://stackoverflow.com/questions/32956577/d3-js-or-sigmajs-is-more-good-for-network-visualisation</ins>](https://stackoverflow.com/questions/32956577/d3-js-or-sigmajs-is-more-good-for-network-visualisation)
    
31. D3 by Observable | The JavaScript library for bespoke data visualization, 10月 21, 2025にアクセス、 [<ins>https://d3js.org/</ins>](https://d3js.org/)
    
32. Best Practices for Optimizing WebSockets Performance - PixelFreeStudio Blog, 10月 21, 2025にアクセス、 [<ins>https://blog.pixelfreestudio.com/best-practices-for-optimizing-websockets-performance/</ins>](https://blog.pixelfreestudio.com/best-practices-for-optimizing-websockets-performance/)
    
33. Synchronizing state with Websockets and JSON Patch - cetra3, 10月 21, 2025にアクセス、 [<ins>https://cetra3.github.io/blog/synchronising-with-websocket/</ins>](https://cetra3.github.io/blog/synchronising-with-websocket/)
    
34. WebSockets - FastAPI, 10月 21, 2025にアクセス、 [<ins>https://fastapi.tiangolo.com/advanced/websockets/</ins>](https://fastapi.tiangolo.com/advanced/websockets/)
    
35. Managing Per-User WebSocket State in FastAPI | by Hex Shift ..., 10月 21, 2025にアクセス、 [<ins>https://medium.com/@hexshift/managing-per-user-websocket-state-in-fastapi-9ceaa2b312ac</ins>](https://medium.com/@hexshift/managing-per-user-websocket-state-in-fastapi-9ceaa2b312ac)
    
36. Building an Optimistic UI with RxDB | RxDB - JavaScript Database, 10月 21, 2025にアクセス、 [<ins>https://rxdb.info/articles/optimistic-ui.html</ins>](https://rxdb.info/articles/optimistic-ui.html)
    
37. Fully reactive, optimistic by default and resilient WebSocket library & sync engine (Open-Source) : r/webdev - Reddit, 10月 21, 2025にアクセス、 [<ins>https://www.reddit.com/r/webdev/comments/1m3kzog/fully_reactive_optimistic_by_default_and/</ins>](https://www.reddit.com/r/webdev/comments/1m3kzog/fully_reactive_optimistic_by_default_and/)
    
38. Securing FastAPI with JWT Token-based Authentication | TestDriven.io, 10月 21, 2025にアクセス、 [<ins>https://testdriven.io/blog/fastapi-jwt-auth/</ins>](https://testdriven.io/blog/fastapi-jwt-auth/)
    
39. OAuth2 with Password (and hashing), Bearer with JWT tokens - FastAPI, 10月 21, 2025にアクセス、 [<ins>https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/</ins>](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
    
40. Understanding jwt tokens : r/FastAPI - Reddit, 10月 21, 2025にアクセス、 [<ins>https://www.reddit.com/r/FastAPI/comments/1np8b7c/understanding_jwt_tokens/</ins>](https://www.reddit.com/r/FastAPI/comments/1np8b7c/understanding_jwt_tokens/)
    
41. Building a Secure FastAPI Client: A Practical Guide to Token ..., 10月 21, 2025にアクセス、 [<ins>https://medium.com/@amirrdoustdar1/building-a-secure-fastapi-client-a-practical-guide-to-token-refresh-and-authentication-cab2820cc418</ins>](https://medium.com/@amirrdoustdar1/building-a-secure-fastapi-client-a-practical-guide-to-token-refresh-and-authentication-cab2820cc418)
    
42. How to Manage JWT Expiration and Revoke JWTs | FusionAuth, 10月 21, 2025にアクセス、 [<ins>https://fusionauth.io/articles/tokens/revoking-jwts</ins>](https://fusionauth.io/articles/tokens/revoking-jwts)
    
43. oauth 2.0 - How can I revoke a JWT token? - Stack Overflow, 10月 21, 2025にアクセス、 [<ins>https://stackoverflow.com/questions/31919067/how-can-i-revoke-a-jwt-token</ins>](https://stackoverflow.com/questions/31919067/how-can-i-revoke-a-jwt-token)
    
44. Best practice for checking if token is revoked in API - Auth0 Community, 10月 21, 2025にアクセス、 [<ins>https://community.auth0.com/t/best-practice-for-checking-if-token-is-revoked-in-api/17460</ins>](https://community.auth0.com/t/best-practice-for-checking-if-token-is-revoked-in-api/17460)
    
45. JWT Token Revocation - DZone, 10月 21, 2025にアクセス、 [<ins>https://dzone.com/articles/jwt-token-revocation</ins>](https://dzone.com/articles/jwt-token-revocation)
    
46. Best of 2021 - How to Revoke JSON Web Tokens (JWTs) - DevOps.com, 10月 21, 2025にアクセス、 [<ins>https://devops.com/how-to-revoke-json-web-tokens-jwts/</ins>](https://devops.com/how-to-revoke-json-web-tokens-jwts/)
