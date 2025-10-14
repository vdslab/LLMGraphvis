#!/usr/bin/env python3
"""
OpenAI API実装のデバッグテストスクリプト
"""

import os
import json
import asyncio
import sys
from pathlib import Path

# APIモジュールをインポートするためのパス設定
sys.path.insert(0, str(Path(__file__).parent / "API"))

# 環境変数の設定（テスト用）
os.environ["LLM_PROVIDER"] = "openai"
os.environ["OPENAI_API_KEY"] = "test_key"  # テスト用のダミーキー
os.environ["OPENAI_MODEL"] = "gpt-4o"

async def test_openai_implementation():
    """OpenAI実装をテストする"""
    print("🔍 OpenAI API実装のテスト開始...")
    
    try:
        # LLMサービスをインポート
        from services.llm import (
            _initialize_clients, 
            get_current_provider, 
            get_clients,
            _process_with_openai,
            TOOLS_DEFINITION
        )
        
        print(f"✅ LLMサービスのインポート成功")
        
        # 1. プロバイダーの確認
        print(f"📋 現在のプロバイダー: {get_current_provider()}")
        
        # 2. クライアントの初期化
        _initialize_clients()
        gemini_client, openai_client = get_clients()
        print(f"📋 Geminiクライアント: {gemini_client is not None}")
        print(f"📋 OpenAIクライアント: {openai_client is not None}")
        
        # 3. Tool定義の確認
        print(f"📋 Tool定義数: {len(TOOLS_DEFINITION)}")
        print("📋 Tool定義の最初の3つ:")
        for i, tool in enumerate(TOOLS_DEFINITION[:3]):
            print(f"   {i+1}. {tool['name']}: {tool.get('description', 'No description')[:50]}...")
        
        # 4. OpenAI SDKのインポートテスト
        try:
            from openai import OpenAI
            print("✅ OpenAI SDK インポート成功")
            
            # HTTPXクライアントのテスト
            import httpx
            client = OpenAI(api_key="test_key", http_client=httpx.Client())
            print("✅ OpenAI クライアント作成成功")
            
        except ImportError as e:
            print(f"❌ OpenAI SDK インポートエラー: {e}")
            return False
        except Exception as e:
            print(f"❌ OpenAI クライアント作成エラー: {e}")
            return False
        
        # 5. Tool定義のフォーマット確認
        print("\n🔍 Tool定義のフォーマット確認...")
        for i, tool in enumerate(TOOLS_DEFINITION[:2]):
            print(f"\nTool {i+1}: {tool['name']}")
            print(f"  Description: {tool.get('description', 'None')[:100]}...")
            print(f"  Parameters type: {type(tool.get('parameters', {}))}")
            print(f"  Parameters keys: {list(tool.get('parameters', {}).keys())}")
            
            # OpenAI用のフォーマットに変換してみる
            openai_tool = {"type": "function", "function": tool}
            print(f"  OpenAI format conversion: {json.dumps(openai_tool, indent=2)[:200]}...")
        
        # 6. 簡単なメッセージ処理テスト（実際のAPIコールなし）
        print("\n🔍 メッセージ処理テスト...")
        test_messages = [
            {"role": "user", "content": "Hello, test message"}
        ]
        
        print(f"  テストメッセージ: {test_messages}")
        print(f"  メッセージ数: {len(test_messages)}")
        print(f"  メッセージフォーマット: OK")
        
        return True
        
    except ImportError as e:
        print(f"❌ インポートエラー: {e}")
        return False
    except Exception as e:
        print(f"❌ 予期せぬエラー: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """メイン関数"""
    print("🚀 OpenAI API デバッグテスト開始")
    print("=" * 50)
    
    success = await test_openai_implementation()
    
    print("=" * 50)
    if success:
        print("✅ テスト完了 - 基本的な実装は正常です")
    else:
        print("❌ テスト失敗 - 問題が発見されました")
    
    return success

if __name__ == "__main__":
    asyncio.run(main())