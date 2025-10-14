#!/usr/bin/env python3
"""
認証付きでAPIエンドポイントをテストするスクリプト
"""

import requests
import json

def get_auth_token():
    """テスト用の認証トークンを取得"""
    api_url = "http://localhost:8000"
    
    # テスト用ユーザーでログイン
    login_data = {
        "username": "test@example.com",
        "password": "testpassword"
    }
    
    try:
        # ログインしてトークンを取得
        response = requests.post(f"{api_url}/auth/login", data=login_data)
        if response.status_code == 200:
            result = response.json()
            return result.get("access_token")
        else:
            print(f"Login failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error during login: {e}")
        return None

def test_api_with_auth():
    """認証付きでAPIエンドポイントをテスト"""
    api_url = "http://localhost:8000"
    
    # 認証トークンを取得
    token = get_auth_token()
    if not token:
        print("❌ Failed to get authentication token")
        return False
    
    print(f"✅ Got authentication token: {token[:20]}...")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # テスト用ネットワークデータ
    request_data = {
        "network": {
            "nodes": [
                {"id": "0", "label": "Center Node"},
                {"id": "1", "label": "Node 1"},
                {"id": "2", "label": "Node 2"},
                {"id": "3", "label": "Node 3"},
                {"id": "4", "label": "Node 4"}
            ],
            "edges": [
                {"source": "0", "target": "1"},
                {"source": "0", "target": "2"},
                {"source": "0", "target": "3"},
                {"source": "0", "target": "4"}
            ]
        },
        "centrality_type": "degree",
        "color_scheme": "viridis",
        "size_range": [30, 80]
    }
    
    try:
        print("📊 Testing authenticated direct centrality calculation")
        response = requests.post(
            f"{api_url}/network/calculate-centrality-direct",
            json=request_data,
            headers=headers,
            timeout=60.0
        )
        
        print(f"   Status Code: {response.status_code}")
        print(f"   Raw Response: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   Parsed Response: {json.dumps(result, indent=2)}")
            
            if result.get("success") and "visualization_data" in result:
                viz_data = result["visualization_data"]
                print(f"   ✅ Success! visualization_data: {len(viz_data)} nodes")
                
                # ノードサイズの確認
                center_node = viz_data.get("0", {})
                other_nodes = [viz_data.get(str(i), {}) for i in range(1, 5)]
                
                center_size = center_node.get("size", 0)
                other_sizes = [node.get("size", 0) for node in other_nodes]
                
                print(f"   Center node size: {center_size}")
                print(f"   Other nodes sizes: {other_sizes}")
                
                if center_size > max(other_sizes):
                    print("   ✅ Center node has larger size (correct centrality visualization)")
                    return True
                else:
                    print("   ❌ Center node does not have larger size")
            else:
                print("   ❌ Response does not contain visualization_data")
        else:
            print(f"   ❌ API request failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return False

def create_test_user():
    """テスト用ユーザーを作成"""
    api_url = "http://localhost:8000"
    
    user_data = {
        "email": "test@example.com",
        "password": "testpassword",
        "full_name": "Test User"
    }
    
    try:
        response = requests.post(f"{api_url}/auth/register", json=user_data)
        if response.status_code == 200:
            print("✅ Test user created successfully")
            return True
        elif response.status_code == 400 and "already registered" in response.text:
            print("✅ Test user already exists")
            return True
        else:
            print(f"❌ Failed to create test user: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error creating test user: {e}")
        return False

def main():
    print("🧪 Testing Centrality Visualization with Authentication")
    print("=" * 60)
    
    # テストユーザーを作成
    if not create_test_user():
        print("❌ Failed to create test user. Exiting.")
        return
    
    # 認証付きでAPIをテスト
    success = test_api_with_auth()
    
    print(f"\n📈 Test Result: {'✅ PASS' if success else '❌ FAIL'}")
    
    if success:
        print("\n🎉 Authentication and centrality visualization are working correctly!")
    else:
        print("\n⚠️ Test failed. Please check the authentication and API implementation.")

if __name__ == "__main__":
    main()