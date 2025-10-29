# DocusaurusにAlgolia DocSearchおよびAsk AIを導入する手順

このドキュメントでは、Docusaurusで構築されたウェブサイトにAlgolia DocSearchおよびAsk AIを導入する手順について説明します。

## 1. Algolia DocSearchへの申請

まず、[Algolia DocSearchの公式サイト](https://docsearch.algolia.com/apply/)から、あなたのウェブサイトをクロールしてもらうための申請を行います。
このサービスは、オープンソースプロジェクトや技術ブログであれば無料で利用できます。

申請が承認されると、Algoliaから以下の3つの情報がメールで送られてきます。これらは後のステップで必要になります。

-   `appId`
-   `apiKey`
-   `indexName`

**重要:** ここで発行される`apiKey`は、**検索専用（Search-Only）**のキーです。このキーは、データの追加や削除などの書き込み操作は許可されておらず、公開されても安全です。

## 2. Algolia Ask AIのセットアップ (オプション)

検索機能に加えて、AIによる対話型の回答機能を導入したい場合は、Algolia Ask AIをセットアップします。

1.  Algoliaのダッシュボードにログインし、「Data Sources」セクションから「Ask AI」を選択します。
2.  「Create Your Assistant」をクリックし、画面の指示に従って設定を進めます。
    -   **LLM Providerの選択:** OpenAIやAnthropicなど、利用したい言語モデルのプロバイダーを選択し、APIキーを設定します。
    -   **System Promptの設定:** アシスタントの振る舞いを定義するプロンプトを設定します。テンプレートを利用するか、独自に作成できます。
3.  設定が完了すると、アシスタントの一覧画面で**Assistant ID**が確認できます。このIDをコピーしてください。後のステップで環境変数として設定します。

この機能はオプションであり、設定しない場合は従来のDocSearchのみが有効になります。

## 3. 環境変数の設定 (ローカル環境)

受け取ったAlgoliaの認証情報を安全に管理するため、プロジェクトのルートディレクトリに`.env`という名前のファイルを作成します。

このファイルは`.gitignore`によってGitの管理対象から除外されているため、誤ってリポジトリにコミットされることはありません。

`.env`ファイルに、以下のようにAlgoliaから受け取った情報を記述します。

```bash
# .env

ALGOLIA_APP_ID=YOUR_APP_ID
ALGOLIA_API_KEY=YOUR_SEARCH_API_KEY
ALGOLIA_INDEX_NAME=YOUR_INDEX_NAME

# Ask AIを利用する場合 (オプション)
ALGOLIA_ASK_AI_ASSISTANT_ID=YOUR_ALGOLIA_ASK_AI_ASSISTANT_ID
```

`YOUR_`で始まる各部分を、実際に受け取った値に置き換えてください。

プロジェクトには`.env.example`ファイルが含まれており、必要な環境変数のテンプレートとして参照できます。

## 4. Docusaurusの設定確認

`docusaurus.config.ts`ファイルには、環境変数を読み込み、Algolia DocSearchおよびAsk AIを有効にするための設定が記述されています。

環境変数が設定されている場合にのみ各機能が有効になるように、設定は条件付きで読み込まれます。

```typescript
// docusaurus.config.ts
import "dotenv/config";

// ...

const config: Config = {
  // ...
  themeConfig: {
    // ...
    ...(process.env.ALGOLIA_APP_ID
      ? {
          algolia: {
            appId: process.env.ALGOLIA_APP_ID,
            apiKey: process.env.ALGOLIA_API_KEY!,
            indexName: process.env.ALGOLIA_INDEX_NAME!,
            contextualSearch: true,
            ...(process.env.ALGOLIA_ASK_AI_ASSISTANT_ID
              ? {
                  askAi: {
                    assistantId: process.env.ALGOLIA_ASK_AI_ASSISTANT_ID,
                  },
                }
              : {}),
          },
        }
      : {}),
    // ...
  },
  // ...
};

export default config;
```

`import "dotenv/config";`という行がファイルの先頭に追加されており、これにより`process.env`オブジェクトを通じて`.env`ファイルの値にアクセスできるようになっています。

## 5. 動作確認 (ローカル環境)

設定が完了したら、ローカル環境で開発サーバーを起動して、検索バーが正しく表示されるか確認します。

以下のコマンドを実行してください。

```bash
npm install
npm start
```

ブラウザで`http://localhost:3030`にアクセスし、サイトのヘッダーに検索バーが表示されていれば、設定は成功です。Ask AIを有効にした場合は、検索モーダル内にAIに質問するためのインターフェースが表示されます。

## 6. Netlifyへのデプロイ

### 環境変数の設定

Netlifyなどのホスティングサービスにデプロイする際には、ローカルの`.env`ファイルは読み込まれません。そのため、サービスの管理画面で環境変数を設定する必要があります。

Netlifyの場合、「Site settings」>「Build & deploy」>「Environment」>「Environment variables」から、以下の環境変数を設定してください。

-   `ALGOLIA_APP_ID`
-   `ALGOLIA_API_KEY`
-   `ALGOLIA_INDEX_NAME`
-   `ALGOLIA_ASK_AI_ASSISTANT_ID` (Ask AIを利用する場合)

### シークレットスキャンの設定

Netlifyは、ビルド後のファイルにAPIキーなどの機密情報が含まれていると、セキュリティ上の理由からデプロイを自動的に停止する「シークレットスキャン」機能を備えています。

Docusaurusの仕様上、AlgoliaのAPIキーはビルドされたHTMLファイルに埋め込まれます。前述の通り、このキーは検索専用で公開されても安全ですが、Netlifyのスキャナーはそれを区別できないため、デプロイが失敗します。

この問題を解決するため、プロジェクトのルートに`netlify.toml`ファイルを作成し、特定の値がスキャンされてもエラーにしないよう設定しています。

```toml
# netlify.toml

[build.environment]
  SECRETS_SCAN_OMIT_KEYS = "ALGOLIA_API_KEY,ALGOLIA_APP_ID,ALGOLIA_INDEX_NAME,REVIEW_ID,ALGOLIA_ASK_AI_ASSISTANT_ID"
```

これにより、Netlifyは指定されたキーをシークレットとは見なさなくなり、ビルドが正常に完了します。

**注意:** Algoliaのクローラーがあなたのサイトをクロールするまで、検索機能は正しく動作しません。クロールのスケジュールはAlgoliaのダッシュボードから確認・変更できます。
