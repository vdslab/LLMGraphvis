#!/bin/bash

# LLMGraphvis Setup Script (Dockerなし)
# このスクリプトは初回セットアップ時に実行してください

set -e  # エラーが発生したら即座に終了

echo "=========================================="
echo "LLMGraphvis セットアップスクリプト"
echo "=========================================="
echo ""

# カラー定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 前提条件のチェック
echo "前提条件をチェックしています..."

# Python 3.12+ のチェック
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}エラー: Python 3がインストールされていません${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
REQUIRED_VERSION="3.12"
if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo -e "${RED}エラー: Python 3.12以上が必要です (現在: $PYTHON_VERSION)${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python $PYTHON_VERSION${NC}"

# Node.js のチェック
if ! command -v node &> /dev/null; then
    echo -e "${RED}エラー: Node.jsがインストールされていません${NC}"
    exit 1
fi
NODE_VERSION=$(node --version)
echo -e "${GREEN}✓ Node.js $NODE_VERSION${NC}"

# PostgreSQL のチェック
if ! command -v psql &> /dev/null; then
    echo -e "${RED}エラー: PostgreSQLがインストールされていません${NC}"
    echo "Homebrewでインストールする場合: brew install postgresql@15"
    exit 1
fi
echo -e "${GREEN}✓ PostgreSQL インストール済み${NC}"

# PostgreSQLが起動しているかチェック
if ! pg_isready -q; then
    echo -e "${YELLOW}警告: PostgreSQLが起動していません${NC}"
    echo "PostgreSQLを起動しています..."
    if command -v brew &> /dev/null; then
        brew services start postgresql@15 || brew services start postgresql
    else
        echo -e "${RED}PostgreSQLを手動で起動してください${NC}"
        exit 1
    fi
    sleep 3
fi
echo -e "${GREEN}✓ PostgreSQL 起動中${NC}"

echo ""
echo "=========================================="
echo "環境変数ファイルのセットアップ"
echo "=========================================="

# .envファイルの作成
if [ ! -f .env ]; then
    echo ".envファイルを作成しています..."
    cp .env.example .env
    
    # ローカル環境用にDATABASE_URLとNETWORKX_MCP_URLを更新
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' 's|DATABASE_URL=postgresql://postgres:postgres@db:5432/graphvis|DATABASE_URL=postgresql://postgres:postgres@localhost:5432/graphvis|g' .env
    else
        # Linux
        sed -i 's|DATABASE_URL=postgresql://postgres:postgres@db:5432/graphvis|DATABASE_URL=postgresql://postgres:postgres@localhost:5432/graphvis|g' .env
    fi
    
    # NETWORKX_MCP_URLを追加
    echo "" >> .env
    echo "# NetworkXMCP Server URL (for local development)" >> .env
    echo "NETWORKX_MCP_URL=http://localhost:8001" >> .env
    
    echo -e "${GREEN}✓ .envファイルを作成しました${NC}"
    echo -e "${YELLOW}注意: .envファイルを編集して、API_KEYを設定してください${NC}"
else
    echo -e "${GREEN}✓ .envファイルは既に存在します${NC}"
fi

echo ""
echo "=========================================="
echo "PostgreSQLデータベースのセットアップ"
echo "=========================================="

# PostgreSQLのデフォルトユーザーを検出
PGUSER="${USER}"
if psql -U postgres -l &>/dev/null; then
    PGUSER="postgres"
fi
echo "PostgreSQLユーザー: $PGUSER"

# データベースとユーザーの作成
echo "データベースとユーザーを作成しています..."

# データベースが既に存在するかチェック
DB_EXISTS=$(psql -U "$PGUSER" -lqt 2>/dev/null | cut -d \| -f 1 | grep -w graphvis | wc -l)
if [ "$DB_EXISTS" -gt 0 ]; then
    echo -e "${YELLOW}データベース 'graphvis' は既に存在します${NC}"
    read -p "データベースを再作成しますか？ (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        psql -U "$PGUSER" -c "DROP DATABASE IF EXISTS graphvis;" 2>/dev/null || true
        psql -U "$PGUSER" -c "CREATE DATABASE graphvis;" 2>/dev/null || true
        echo -e "${GREEN}✓ データベースを再作成しました${NC}"
    fi
else
    psql -U "$PGUSER" -c "CREATE DATABASE graphvis;" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ データベースを作成しました${NC}"
    else
        echo -e "${RED}エラー: データベースの作成に失敗しました${NC}"
        exit 1
    fi
fi

# postgresユーザーが存在しない場合は作成
if ! psql -U "$PGUSER" -d graphvis -tAc "SELECT 1 FROM pg_roles WHERE rolname='postgres'" | grep -q 1; then
    echo "postgresユーザーを作成しています..."
    psql -U "$PGUSER" -d graphvis -c "CREATE USER postgres WITH PASSWORD 'postgres';" 2>/dev/null || true
    psql -U "$PGUSER" -d graphvis -c "GRANT ALL PRIVILEGES ON DATABASE graphvis TO postgres;" 2>/dev/null || true
    echo -e "${GREEN}✓ postgresユーザーを作成しました${NC}"
fi

# テーブルの初期化
echo "テーブルを初期化しています..."
psql -U "$PGUSER" -d graphvis -f API/init.sql
echo -e "${GREEN}✓ テーブルを初期化しました${NC}"

echo ""
echo "=========================================="
echo "APIサーバーのセットアップ"
echo "=========================================="

cd API

# 仮想環境の作成
if [ ! -d .venv ]; then
    echo "Python仮想環境を作成しています..."
    python3 -m venv .venv
    echo -e "${GREEN}✓ 仮想環境を作成しました${NC}"
else
    echo -e "${GREEN}✓ 仮想環境は既に存在します${NC}"
fi

# 依存関係のインストール
echo "依存関係をインストールしています..."
.venv/bin/pip install --upgrade pip setuptools wheel
.venv/bin/pip install 'uvicorn[standard]' fastapi 'python-jose[cryptography]' 'passlib[bcrypt]' 'bcrypt==3.2.0' sqlalchemy psycopg2-binary httpx python-dotenv 'openai==1.3.0' google-genai networkx pydantic starlette 'anyio==3.6.2' alembic
echo -e "${GREEN}✓ APIサーバーの依存関係をインストールしました${NC}"

cd ..

echo ""
echo "=========================================="
echo "NetworkXMCPサーバーのセットアップ"
echo "=========================================="

cd NetworkXMCP

# 仮想環境の作成
if [ ! -d .venv ]; then
    echo "Python仮想環境を作成しています..."
    python3 -m venv .venv
    echo -e "${GREEN}✓ 仮想環境を作成しました${NC}"
else
    echo -e "${GREEN}✓ 仮想環境は既に存在します${NC}"
fi

# 依存関係のインストール
echo "依存関係をインストールしています..."
.venv/bin/pip install --upgrade pip setuptools wheel
.venv/bin/pip install 'uvicorn[standard]' fastapi networkx numpy pydantic fastapi-mcp
echo -e "${GREEN}✓ NetworkXMCPサーバーの依存関係をインストールしました${NC}"

cd ..

echo ""
echo "=========================================="
echo "フロントエンドのセットアップ"
echo "=========================================="

cd frontend

# Node.js依存関係のインストール
if [ ! -d node_modules ]; then
    echo "Node.js依存関係をインストールしています..."
    npm install
    echo -e "${GREEN}✓ フロントエンドの依存関係をインストールしました${NC}"
else
    echo -e "${GREEN}✓ node_modulesは既に存在します${NC}"
fi

cd ..

echo ""
echo "=========================================="
echo "セットアップ完了！"
echo "=========================================="
echo ""
echo -e "${GREEN}すべてのセットアップが完了しました！${NC}"
echo ""
echo "次のステップ:"
echo "1. .envファイルを編集して、API_KEYを設定してください"
echo "2. ./start.sh を実行してアプリケーションを起動してください"
echo ""
