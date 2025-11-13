# 共通ロギング設定設計

## 概要

このドキュメントでは、LLMGraphvisプロジェクトで使用する共通ロギング設定の設計について説明します。ロギング設定を統一することで、一貫したログ出力を確保し、デバッグやモニタリングを容易にします。

## 設計目標

1. **一貫性**: API側とNetworkXMCP側で一貫したログ形式を提供する
2. **柔軟性**: 環境に応じてログレベルを調整できるようにする
3. **構造化**: 構造化ログを出力し、分析を容易にする
4. **コンテキスト**: ログにコンテキスト情報を含める
5. **パフォーマンス**: ロギングによるパフォーマンスへの影響を最小限に抑える

## ロギング設定の構成

### 1. ロガー階層

```
root
├── api
│   ├── routers
│   │   ├── auth
│   │   ├── network
│   │   └── chat
│   ├── services
│   │   ├── graphml
│   │   ├── visualization
│   │   ├── layout
│   │   ├── mcp_client
│   │   └── llm
│   └── core
├── networkx_mcp
│   ├── tools
│   ├── layouts
│   ├── metrics
│   ├── graphml
│   └── cache
└── common
    ├── utils
    ├── models
    └── exceptions
```

### 2. ログレベル

| レベル | 用途 |
|-------|------|
| `CRITICAL` | アプリケーションが動作を継続できない致命的なエラー |
| `ERROR` | エラー発生時（例外キャッチ時など） |
| `WARNING` | 潜在的な問題や注意が必要な状況 |
| `INFO` | 一般的な情報（リクエスト処理開始/終了など） |
| `DEBUG` | デバッグ情報（変数の値、処理の詳細など） |
| `TRACE` | 非常に詳細なデバッグ情報（関数の入出力など） |

### 3. ログフォーマット

#### 基本フォーマット

```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

#### JSON構造化フォーマット

```json
{
  "timestamp": "2025-11-13T05:15:00.000Z",
  "level": "INFO",
  "logger": "api.routers.network",
  "message": "Processing network upload",
  "context": {
    "request_id": "1234-5678-90ab-cdef",
    "user_id": 42,
    "file_size": 1024
  },
  "extra": {
    "process_id": 1234,
    "thread_id": 5678
  }
}
```

## 実装設計

### 1. 共通ロギング設定モジュール

```python
# common/logging/config.py

import os
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional

# カスタムログレベル
TRACE = 5
logging.addLevelName(TRACE, "TRACE")

def trace(self, message, *args, **kwargs):
    """
    TRACEレベルのログを出力する。
    """
    if self.isEnabledFor(TRACE):
        self._log(TRACE, message, args, **kwargs)

logging.Logger.trace = trace

class ContextAdapter(logging.LoggerAdapter):
    """
    コンテキスト情報を含めるためのアダプター。
    """
    def process(self, msg, kwargs):
        context = kwargs.pop('context', {})
        if self.extra:
            context.update(self.extra)
        kwargs["extra"] = {"context": context}
        return msg, kwargs

class JsonFormatter(logging.Formatter):
    """
    JSON形式でログを出力するフォーマッター。
    """
    def format(self, record):
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "process_id": record.process,
            "thread_id": record.thread
        }
        
        # コンテキスト情報を追加
        if hasattr(record, "context"):
            log_data["context"] = record.context
        
        # 例外情報を追加
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }
        
        return json.dumps(log_data)

def get_log_level() -> int:
    """
    環境変数からログレベルを取得する。
    """
    log_level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_levels = {
        "TRACE": TRACE,
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    return log_levels.get(log_level_str, logging.INFO)

def configure_logging(
    use_json: bool = False,
    log_file: Optional[str] = None
) -> None:
    """
    ロギングを設定する。
    
    Args:
        use_json: JSON形式でログを出力するかどうか
        log_file: ログファイルのパス
    """
    log_level = get_log_level()
    
    # ルートロガーの設定
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # 既存のハンドラをクリア
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # コンソールハンドラの設定
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    
    # フォーマッターの設定
    if use_json:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # ファイルハンドラの設定（指定された場合）
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # 主要なロガーの設定
    loggers = [
        "api",
        "api.routers",
        "api.services",
        "api.core",
        "networkx_mcp",
        "networkx_mcp.tools",
        "networkx_mcp.layouts",
        "networkx_mcp.metrics",
        "networkx_mcp.graphml",
        "networkx_mcp.cache",
        "common",
        "common.utils",
        "common.models",
        "common.exceptions"
    ]
    
    for logger_name in loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(log_level)
        logger.propagate = True

def get_logger(name: str, context: Optional[Dict[str, Any]] = None):
    """
    指定された名前とコンテキストでロガーを取得する。
    
    Args:
        name: ロガー名
        context: ログに含めるコンテキスト情報
        
    Returns:
        ContextAdapter: コンテキスト情報を含むロガーアダプター
    """
    logger = logging.getLogger(name)
    return ContextAdapter(logger, context or {})
```

### 2. ロギングフォーマッター

```python
# common/logging/formatters.py

import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional

class StandardFormatter(logging.Formatter):
    """
    標準的なログフォーマッター。
    """
    def __init__(self, include_process_info: bool = False):
        super().__init__()
        self.include_process_info = include_process_info
    
    def format(self, record):
        if self.include_process_info:
            fmt = "%(asctime)s - %(name)s - %(levelname)s - [%(process)d:%(thread)d] - %(message)s"
        else:
            fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        
        formatter = logging.Formatter(fmt)
        return formatter.format(record)

class DetailedFormatter(logging.Formatter):
    """
    詳細なログフォーマッター。
    """
    def format(self, record):
        fmt = (
            "%(asctime)s - %(name)s - %(levelname)s - "
            "%(module)s:%(funcName)s:%(lineno)d - %(message)s"
        )
        formatter = logging.Formatter(fmt)
        return formatter.format(record)

class JsonFormatter(logging.Formatter):
    """
    JSON形式でログを出力するフォーマッター。
    """
    def __init__(self, include_traceback: bool = True):
        super().__init__()
        self.include_traceback = include_traceback
    
    def format(self, record):
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "process_id": record.process,
            "thread_id": record.thread
        }
        
        # コンテキスト情報を追加
        if hasattr(record, "context"):
            log_data["context"] = record.context
        
        # 例外情報を追加
        if record.exc_info and self.include_traceback:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }
        
        return json.dumps(log_data)

def get_formatter(
    format_type: str = "standard",
    include_process_info: bool = False,
    include_traceback: bool = True
) -> logging.Formatter:
    """
    指定された形式のフォーマッターを取得する。
    
    Args:
        format_type: フォーマッターの種類（"standard", "detailed", "json"）
        include_process_info: プロセス情報を含めるかどうか
        include_traceback: トレースバックを含めるかどうか
        
    Returns:
        logging.Formatter: 指定された形式のフォーマッター
    """
    if format_type == "detailed":
        return DetailedFormatter()
    elif format_type == "json":
        return JsonFormatter(include_traceback=include_traceback)
    else:
        return StandardFormatter(include_process_info=include_process_info)
```

## 使用例

### 1. アプリケーション起動時の設定

```python
# API/main.py

import os
from fastapi import FastAPI
from common.logging.config import configure_logging

# 環境変数からJSON形式を使用するかどうかを取得
use_json = os.environ.get("LOG_FORMAT", "").lower() == "json"

# ロギングを設定
configure_logging(use_json=use_json, log_file="api.log")

app = FastAPI()
# ...
```

```python
# NetworkXMCP/main.py

import os
from fastapi import FastAPI
from common.logging.config import configure_logging

# 環境変数からJSON形式を使用するかどうかを取得
use_json = os.environ.get("LOG_FORMAT", "").lower() == "json"

# ロギングを設定
configure_logging(use_json=use_json, log_file="networkx_mcp.log")

app = FastAPI()
# ...
```

### 2. ロガーの使用

```python
# API/routers/network/upload.py

from fastapi import APIRouter, Depends, File, UploadFile
from common.logging.config import get_logger

router = APIRouter()

@router.post("/upload")
async def upload_network(file: UploadFile = File(...)):
    # リクエスト固有のコンテキスト情報を含むロガーを取得
    logger = get_logger("api.routers.network.upload", {
        "file_name": file.filename,
        "content_type": file.content_type,
        "file_size": file.size
    })
    
    logger.info("Processing network upload request")
    
    try:
        # ファイル処理
        content = await file.read()
        logger.debug(f"Read {len(content)} bytes from file")
        
        # 処理結果
        result = {"success": True, "file_name": file.filename}
        logger.info("Network upload successful", context={"result": result})
        return result
    except Exception as e:
        logger.error(f"Error processing network upload: {str(e)}", exc_info=True)
        raise
```

### 3. 構造化ロギングの使用

```python
# NetworkXMCP/tools/parsing.py

from common.logging.config import get_logger
from typing import Dict, Any

def parse_graphml(graphml_content: str) -> Dict[str, Any]:
    logger = get_logger("networkx_mcp.tools.parsing")
    
    logger.info("Parsing GraphML content", context={
        "content_length": len(graphml_content)
    })
    
    try:
        # GraphMLパース処理
        # ...
        
        result = {
            "nodes": 10,
            "edges": 15,
            "attributes": ["name", "weight"]
        }
        
        logger.info("GraphML parsing successful", context={
            "node_count": result["nodes"],
            "edge_count": result["edges"]
        })
        
        return result
    except Exception as e:
        logger.error("GraphML parsing failed", context={
            "error_type": type(e).__name__,
            "error_message": str(e)
        }, exc_info=True)
        raise
```

## 環境変数

| 環境変数 | 説明 | デフォルト値 |
|---------|------|------------|
| `LOG_LEVEL` | ログレベル（TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL） | INFO |
| `LOG_FORMAT` | ログ形式（standard, json） | standard |
| `LOG_FILE` | ログファイルのパス（指定しない場合はコンソールのみ） | なし |

## ロギングのベストプラクティス

1. **適切なログレベルを使用する**
   - `TRACE`: 非常に詳細なデバッグ情報（関数の入出力など）
   - `DEBUG`: デバッグ情報（変数の値、処理の詳細など）
   - `INFO`: 一般的な情報（リクエスト処理開始/終了など）
   - `WARNING`: 潜在的な問題や注意が必要な状況
   - `ERROR`: エラー発生時（例外キャッチ時など）
   - `CRITICAL`: アプリケーションが動作を継続できない致命的なエラー

2. **構造化ロギングを活用する**
   - ログメッセージに加えて、コンテキスト情報を含める
   - JSON形式を使用して、ログの解析を容易にする

3. **例外情報を含める**
   - 例外をキャッチした場合は、`exc_info=True`を指定して例外情報を含める
   - 例外の種類、メッセージ、トレースバックを記録する

4. **パフォーマンスに注意する**
   - ログレベルをチェックしてから、複雑なログメッセージを構築する
   ```python
   if logger.isEnabledFor(logging.DEBUG):
       logger.debug(f"Complex calculation result: {calculate_complex_result()}")
   ```

5. **個人情報や機密情報をログに含めない**
   - パスワード、トークン、個人情報などの機密情報はログに含めない
   - 必要に応じて、機密情報をマスクする

## まとめ

共通ロギング設定を設計することで、以下のメリットが得られます：

1. ログ形式の一貫性
2. 環境に応じたログレベルの調整
3. 構造化ログによる分析の容易化
4. コンテキスト情報の追加
5. パフォーマンスへの影響の最小化

この設計を実装することで、LLMGraphvisプロジェクト全体でロギングが統一され、デバッグやモニタリングが容易になります。