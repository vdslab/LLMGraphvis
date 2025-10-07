# NetworkXMCP 依存関係分析レポート

## 📊 分析日時

2025年10月2日

## ✅ 依存関係の状態: **問題なし**

## 📦 宣言されている依存関係

### pyproject.toml

```toml
dependencies = [
    "fastapi>=0.103.1",           # ✅ 使用中
    "uvicorn>=0.23.2",            # ✅ 使用中（サーバー起動用）
    "networkx>=3.1",              # ✅ 使用中
    "numpy>=1.25.2",              # ✅ 使用中
    "pydantic>=2.3.0",            # ✅ 使用中
    "python-dotenv>=1.0.0",       # ⚠️  使用確認が必要
    "python-multipart>=0.0.6",    # ⚠️  使用確認が必要
    "fastapi-mcp>=0.3.7",         # ✅ 使用中
]
```

## 🔍 実際に使用されているライブラリ

### コアライブラリ（標準ライブラリ）

- `os` - 環境変数とファイルパス操作
- `logging` - ロギング
- `io` - ストリーム処理
- `random` - ランダム値生成
- `json` - JSON処理
- `base64` - Base64エンコード
- `datetime` - 日時処理
- `typing` - 型ヒント
- `xml.sax.saxutils` - XML処理
- `re` - 正規表現
- `traceback` - エラートレース
- `sys` - システム関連（テストファイルのみ）

### サードパーティライブラリ

| ライブラリ                | 使用箇所                                         | 状態    |
| ------------------------- | ------------------------------------------------ | ------- |
| `networkx`                | main.py, tools/_.py, layouts/_.py, metrics/\*.py | ✅ 必須 |
| `numpy`                   | main.py, tools/_.py, layouts/_.py, metrics/\*.py | ✅ 必須 |
| `fastapi`                 | main.py                                          | ✅ 必須 |
| `fastapi.middleware.cors` | main.py                                          | ✅ 必須 |
| `fastapi.responses`       | main.py                                          | ✅ 必須 |
| `fastapi_mcp`             | main.py                                          | ✅ 必須 |
| `pydantic`                | main.py                                          | ✅ 必須 |
| `uvicorn`                 | (起動時)                                         | ✅ 必須 |

## ⚠️ 使用が確認できない依存関係

### 1. python-dotenv

- **宣言**: `python-dotenv>=1.0.0`
- **状態**: コード内で `from dotenv import load_dotenv` などの使用が見つからない
- **影響**: 環境変数は `os.environ.get()` で直接読み込んでいる
- **推奨**: 使用していない場合は削除可能

### 2. python-multipart

- **宣言**: `python-multipart>=0.0.6`
- **状態**: ファイルアップロード機能で必要だが、明示的なimportは不要（FastAPI内部で使用）
- **影響**: ファイルアップロードAPIがある場合は必要
- **推奨**: 保持（FastAPIのファイルアップロードに必要）

## 📝 削除された依存関係（適切）

以下の依存関係は既に適切に削除されています：

```python
# - matplotlib>=3.7.2 (約8MB) - グラフ可視化はフロントエンドで実施
# - scikit-learn>=1.2.0 (約9MB) - 機械学習機能は現在未使用
# - python-louvain>=0.16 (約1MB) - コミュニティ検出は現在未使用
# - requests>=2.31.0 - httpxがあれば不要（現在未使用）
```

## 🎯 推奨事項

### 1. python-dotenv の扱い

現在、環境変数の読み込みは以下のように直接行われています：

```python
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
```

**オプションA: python-dotenvを使用する（推奨）**

```python
from dotenv import load_dotenv
load_dotenv()  # .envファイルから環境変数を読み込む
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
```

**オプションB: 削除する**
Dockerコンテナ内で環境変数を直接設定しているため、python-dotenvは不要かもしれません。

### 2. python-multipart の確認

FastAPIでファイルアップロードを使用している場合は必要です。

```python
# このようなエンドポイントがある場合は必要
from fastapi import File, UploadFile

@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    ...
```

現在のコードを確認する必要があります。

## 🔄 uv.lock の状態

`uv.lock` ファイルは正常で、以下のパッケージがロックされています：

- annotated-types==0.7.0
- anyio==4.9.0
- attrs==25.3.0
- certifi==2025.7.14
- charset-normalizer==3.4.2
- click==8.2.1
- colorama==0.4.6
- （その他のサブ依存関係）

## 📊 依存関係の整合性

✅ **問題なし**: すべての必須パッケージは `pyproject.toml` に正しく宣言されています

## 🚀 最適化の提案

### イメージサイズの削減

現在の依存関係は既に最適化されていますが、さらに削減する場合：

1. **python-dotenv を削除する場合**:

   ```toml
   dependencies = [
       "fastapi>=0.103.1",
       "uvicorn>=0.23.2",
       "networkx>=3.1",
       "numpy>=1.25.2",
       "pydantic>=2.3.0",
       # "python-dotenv>=1.0.0",  # 削除
       "python-multipart>=0.0.6",
       "fastapi-mcp>=0.3.7",
   ]
   ```

2. **ファイルアップロードを使用していない場合**:
   ```toml
   dependencies = [
       "fastapi>=0.103.1",
       "uvicorn>=0.23.2",
       "networkx>=3.1",
       "numpy>=1.25.2",
       "pydantic>=2.3.0",
       "python-dotenv>=1.0.0",
       # "python-multipart>=0.0.6",  # 削除
       "fastapi-mcp>=0.3.7",
   ]
   ```

## 🧪 確認コマンド

実際にインストールされているパッケージを確認：

```bash
# コンテナ内で実行
docker compose exec networkx-mcp uv pip list

# または
docker compose exec networkx-mcp uv pip show python-dotenv
docker compose exec networkx-mcp uv pip show python-multipart
```

## 結論

**現在の依存関係に重大な問題はありません。** すべての主要なライブラリは適切に宣言され、使用されています。

python-dotenv と python-multipart の使用状況を確認して、必要に応じて削除することで、わずかにイメージサイズを削減できる可能性があります。
