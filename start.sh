#!/bin/bash

# LLMGraphvis Start Script (Dockerなし)
# このスクリプトでアプリケーションを起動します

# カラー定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# プロジェクトルートディレクトリ
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$PROJECT_ROOT/.pids"
LOG_DIR="$PROJECT_ROOT/logs"

# ディレクトリの作成
mkdir -p "$PID_DIR"
mkdir -p "$LOG_DIR"

echo "=========================================="
echo "LLMGraphvis 起動スクリプト"
echo "=========================================="
echo ""

# 前提条件のチェック
if [ ! -f .env ]; then
    echo -e "${RED}エラー: .envファイルが見つかりません${NC}"
    echo "まず ./setup.sh を実行してください"
    exit 1
fi

# PostgreSQLが起動しているかチェック
if ! pg_isready -q; then
    echo -e "${YELLOW}PostgreSQLが起動していません。起動しています...${NC}"
    if command -v brew &> /dev/null; then
        brew services start postgresql@15 || brew services start postgresql
        sleep 3
    else
        echo -e "${RED}PostgreSQLを手動で起動してください${NC}"
        exit 1
    fi
fi

# 既存のプロセスをチェック
if [ -f "$PID_DIR/api.pid" ] || [ -f "$PID_DIR/networkx.pid" ] || [ -f "$PID_DIR/frontend.pid" ]; then
    echo -e "${YELLOW}警告: 既に起動中のプロセスがあります${NC}"
    echo "先に ./stop.sh を実行してください"
    exit 1
fi

echo -e "${BLUE}サービスを起動しています...${NC}"
echo ""

# NetworkXMCPサーバーの起動
echo -e "${BLUE}[1/3] NetworkXMCPサーバーを起動しています...${NC}"
cd "$PROJECT_ROOT/NetworkXMCP"
nohup .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8001 --reload > "$LOG_DIR/networkx.log" 2>&1 &
NETWORKX_PID=$!
echo $NETWORKX_PID > "$PID_DIR/networkx.pid"
cd "$PROJECT_ROOT"
echo -e "${GREEN}✓ NetworkXMCPサーバー起動 (PID: $NETWORKX_PID, ポート: 8001)${NC}"
sleep 2

# APIサーバーの起動
echo -e "${BLUE}[2/3] APIサーバーを起動しています...${NC}"
cd "$PROJECT_ROOT/API"
nohup .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload > "$LOG_DIR/api.log" 2>&1 &
API_PID=$!
echo $API_PID > "$PID_DIR/api.pid"
cd "$PROJECT_ROOT"
echo -e "${GREEN}✓ APIサーバー起動 (PID: $API_PID, ポート: 8000)${NC}"
sleep 2

# フロントエンドの起動
echo -e "${BLUE}[3/3] フロントエンドを起動しています...${NC}"
cd "$PROJECT_ROOT/frontend"
nohup npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > "$PID_DIR/frontend.pid"
cd "$PROJECT_ROOT"
echo -e "${GREEN}✓ フロントエンド起動 (PID: $FRONTEND_PID, ポート: 3000)${NC}"

echo ""
echo "=========================================="
echo "起動完了！"
echo "=========================================="
echo ""
echo -e "${GREEN}すべてのサービスが起動しました！${NC}"
echo ""
echo "アクセスURL:"
echo "  - フロントエンド:     http://localhost:3000"
echo "  - APIサーバー:        http://localhost:8000"
echo "  - NetworkXMCPサーバー: http://localhost:8001"
echo ""
echo "ログファイル:"
echo "  - API:        $LOG_DIR/api.log"
echo "  - NetworkXMCP: $LOG_DIR/networkx.log"
echo "  - Frontend:   $LOG_DIR/frontend.log"
echo ""
echo "ログをリアルタイムで確認:"
echo "  tail -f $LOG_DIR/api.log"
echo "  tail -f $LOG_DIR/networkx.log"
echo "  tail -f $LOG_DIR/frontend.log"
echo ""
echo "停止するには:"
echo "  ./stop.sh"
echo ""
