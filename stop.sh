#!/bin/bash

# LLMGraphvis Stop Script (Dockerなし)
# このスクリプトで起動中のアプリケーションを停止します

# カラー定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# プロジェクトルートディレクトリ
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$PROJECT_ROOT/.pids"

echo "=========================================="
echo "LLMGraphvis 停止スクリプト"
echo "=========================================="
echo ""

# PIDファイルが存在するかチェック
if [ ! -d "$PID_DIR" ] || [ -z "$(ls -A $PID_DIR 2>/dev/null)" ]; then
    echo -e "${YELLOW}起動中のプロセスが見つかりません${NC}"
    exit 0
fi

echo -e "${BLUE}サービスを停止しています...${NC}"
echo ""

# フロントエンドの停止
if [ -f "$PID_DIR/frontend.pid" ]; then
    FRONTEND_PID=$(cat "$PID_DIR/frontend.pid")
    echo -e "${BLUE}[1/3] フロントエンドを停止しています... (PID: $FRONTEND_PID)${NC}"
    
    if ps -p $FRONTEND_PID > /dev/null 2>&1; then
        kill $FRONTEND_PID 2>/dev/null || true
        sleep 1
        
        # プロセスがまだ生きている場合は強制終了
        if ps -p $FRONTEND_PID > /dev/null 2>&1; then
            kill -9 $FRONTEND_PID 2>/dev/null || true
        fi
        echo -e "${GREEN}✓ フロントエンド停止${NC}"
    else
        echo -e "${YELLOW}フロントエンドは既に停止しています${NC}"
    fi
    
    rm -f "$PID_DIR/frontend.pid"
fi

# APIサーバーの停止
if [ -f "$PID_DIR/api.pid" ]; then
    API_PID=$(cat "$PID_DIR/api.pid")
    echo -e "${BLUE}[2/3] APIサーバーを停止しています... (PID: $API_PID)${NC}"
    
    if ps -p $API_PID > /dev/null 2>&1; then
        kill $API_PID 2>/dev/null || true
        sleep 1
        
        # プロセスがまだ生きている場合は強制終了
        if ps -p $API_PID > /dev/null 2>&1; then
            kill -9 $API_PID 2>/dev/null || true
        fi
        echo -e "${GREEN}✓ APIサーバー停止${NC}"
    else
        echo -e "${YELLOW}APIサーバーは既に停止しています${NC}"
    fi
    
    rm -f "$PID_DIR/api.pid"
fi

# NetworkXMCPサーバーの停止
if [ -f "$PID_DIR/networkx.pid" ]; then
    NETWORKX_PID=$(cat "$PID_DIR/networkx.pid")
    echo -e "${BLUE}[3/3] NetworkXMCPサーバーを停止しています... (PID: $NETWORKX_PID)${NC}"
    
    if ps -p $NETWORKX_PID > /dev/null 2>&1; then
        kill $NETWORKX_PID 2>/dev/null || true
        sleep 1
        
        # プロセスがまだ生きている場合は強制終了
        if ps -p $NETWORKX_PID > /dev/null 2>&1; then
            kill -9 $NETWORKX_PID 2>/dev/null || true
        fi
        echo -e "${GREEN}✓ NetworkXMCPサーバー停止${NC}"
    else
        echo -e "${YELLOW}NetworkXMCPサーバーは既に停止しています${NC}"
    fi
    
    rm -f "$PID_DIR/networkx.pid"
fi

# uvicornの残存プロセスをクリーンアップ
echo ""
echo -e "${BLUE}残存プロセスをクリーンアップしています...${NC}"
pkill -f "uvicorn main:app" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true

echo ""
echo "=========================================="
echo "停止完了！"
echo "=========================================="
echo ""
echo -e "${GREEN}すべてのサービスを停止しました${NC}"
echo ""
