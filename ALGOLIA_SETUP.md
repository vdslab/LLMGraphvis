# DocusaurusにAlgolia DocSearchを導入する手順

このドキュメントでは、Docusaurusで構築されたウェブサイトにAlgolia DocSearchを導入する手順について説明します。

## 1. Algolia DocSearchへの申請

まず、[Algolia DocSearchの公式サイト](https://docsearch.algolia.com/apply/)から、あなたのウェブサイトをクロールしてもらうための申請を行います。
このサービスは、オープンソースプロジェクトや技術ブログであれば無料で利用できます。

申請が承認されると、Algoliaから以下の3つの情報がメールで送られてきます。これらは後のステップで必要になります。

-   `appId`
-   `apiKey`
-   `indexName`

## 2. 環境変数の設定

受け取ったAlgoliaの認証情報を安全に管理するため、プロジェクトのルートディレクトリに`.env`という名前のファイルを作成します。

このファイルは`.gitignore`によってGitの管理対象から除外されているため、誤ってリポジトリにコミットされることはありません。

`.env`ファイルに、以下のようにAlgoliaから受け取った情報を記述します。

```bash
# .env

ALGOLIA_APP_ID=YOUR_APP_ID
ALGOLIA_API_KEY=YOUR_SEARCH_API_KEY
ALGOLIA_INDEX_NAME=YOUR_INDEX_NAME
```

`YOUR_APP_ID`、`YOUR_SEARCH_API_KEY`、`YOUR_INDEX_NAME`の部分を、実際に受け取った値に置き換えてください。

プロジェクトには`.env.example`ファイルが含まれており、必要な環境変数のテンプレートとして参照できます。

## 3. Docusaurusの設定確認

`docusaurus.config.ts`ファイルには、`.env`ファイルから環境変数を読み込み、Algolia DocSearchを有効にするための設定が既に記述されています。

```typescript
// docusaurus.config.ts
import "dotenv/config";

// ...

const config: Config = {
  // ...
  themeConfig: {
    // ...
    algolia: {
      // The application ID provided by Algolia
      appId: process.env.ALGOLIA_APP_ID!,
      // Public API key: it is safe to commit it
      apiKey: process.env.ALGOLIA_API_KEY!,
      indexName: process.env.ALGOLIA_INDEX_NAME!,
      contextualSearch: true,
    },
    // ...
  },
  // ...
};

export default config;
```

`import "dotenv/config";`という行がファイルの先頭に追加されており、これにより`process.env`オブジェクトを通じて`.env`ファイルの値にアクセスできるようになっています。

`themeConfig.algolia`オブジェクトで、Algoliaの検索機能を設定しています。

## 4. 動作確認

設定が完了したら、ローカル環境で開発サーバーを起動して、検索バーが正しく表示されるか確認します。

以下のコマンドを実行してください。

```bash
npm install
npm start
```

ブラウザで`http://localhost:3030`にアクセスし、サイトのヘッダーに検索バーが表示されていれば、設定は成功です。

**注意:** Algoliaのクローラーがあなたのサイトをクロールするまで、検索機能は正しく動作しません。クロールのスケジュールはAlgoliaのダッシュボードから確認・変更できます。
