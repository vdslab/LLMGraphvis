"""
システム統合テスト

このスクリプトは、システム最終仕様書に基づいて修正されたコードが正しく動作するかをテストします。
特に、フロントエンドとNetworkXMCPサーバーの間の直接通信がないことを確認します。
"""

import unittest
import requests
import json
import os
import time
import subprocess
import signal
from urllib.parse import urlparse

# テスト設定
API_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"
NETWORKX_MCP_URL = "http://localhost:8001"


class SystemIntegrationTest(unittest.TestCase):
    """システム統合テストクラス"""

    @classmethod
    def setUpClass(cls):
        """テスト開始前の準備"""
        print("Checking if services are running...")

        # APIサーバーが起動しているか確認
        try:
            response = requests.get(f"{API_URL}/docs")
            if response.status_code == 200:
                print("API server is running")
            else:
                print(
                    f"API server returned status code {response.status_code}")
        except requests.exceptions.ConnectionError:
            print("API server is not running. Please start the services manually.")
            print("You can start the services with: docker compose up -d")
            raise unittest.SkipTest("Services are not running")

        # NetworkXMCPサーバーが起動しているか確認
        try:
            response = requests.get(f"{NETWORKX_MCP_URL}/health")
            if response.status_code == 200:
                print("NetworkXMCP server is running")
            else:
                print(
                    f"NetworkXMCP server returned status code {response.status_code}")
        except requests.exceptions.ConnectionError:
            print(
                "NetworkXMCP server is not running. Please start the services manually.")
            print("You can start the services with: docker compose up -d")
            raise unittest.SkipTest("Services are not running")

        # テストユーザーを作成
        cls.create_test_user()

        print("Services are running")

    @classmethod
    def tearDownClass(cls):
        """テスト終了後のクリーンアップ"""
        print("Tests completed")

    @classmethod
    def create_test_user(cls):
        """テストユーザーを作成"""
        try:
            response = requests.post(
                f"{API_URL}/auth/register",
                json={"username": "testuser", "password": "testpassword"}
            )
            print(f"Create test user response: {response.status_code}")
            if response.status_code == 200:
                print("Test user created successfully")
            elif response.status_code == 400 and "already exists" in response.text:
                print("Test user already exists")
            else:
                print(f"Failed to create test user: {response.text}")
        except Exception as e:
            print(f"Error creating test user: {e}")

    def get_auth_token(self):
        """認証トークンを取得"""
        response = requests.post(
            f"{API_URL}/auth/token",
            data={"username": "testuser", "password": "testpassword"},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        self.assertEqual(response.status_code, 200, "Failed to get auth token")
        return response.json()["access_token"]

    def test_api_server_running(self):
        """APIサーバーが起動しているかテスト"""
        try:
            response = requests.get(f"{API_URL}/docs")
            self.assertEqual(response.status_code, 200,
                             "API server is not running")
        except requests.exceptions.ConnectionError:
            self.fail("API server is not running")

    def test_networkx_mcp_server_running(self):
        """NetworkXMCPサーバーが起動しているかテスト"""
        try:
            response = requests.get(f"{NETWORKX_MCP_URL}/health")
            self.assertEqual(response.status_code, 200,
                             "NetworkXMCP server is not running")
        except requests.exceptions.ConnectionError:
            self.fail("NetworkXMCP server is not running")

    def test_user_authentication(self):
        """ユーザー認証のテスト"""
        # ログイン
        response = requests.post(
            f"{API_URL}/auth/token",
            data={"username": "testuser", "password": "testpassword"},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        self.assertEqual(response.status_code, 200,
                         "Failed to authenticate user")
        self.assertIn("access_token", response.json(),
                      "No access token in response")

    def test_create_conversation(self):
        """会話作成のテスト"""
        token = self.get_auth_token()

        # 会話を作成
        response = requests.post(
            f"{API_URL}/chat/conversations",
            json={"title": "Test Conversation"},
            headers={"Authorization": f"Bearer {token}"}
        )

        # エラーの詳細を出力
        if response.status_code != 200:
            print(f"Create conversation response: {response.status_code}")
            print(f"Response content: {response.text}")

            # より詳細なエラー情報を取得
            try:
                error_details = response.json()
                print(f"Error details: {error_details}")
            except:
                print("Could not parse error details as JSON")

        self.assertEqual(response.status_code, 200,
                         "Failed to create conversation")

        # レスポンスを検証
        data = response.json()
        self.assertIn("id", data, "No conversation ID in response")
        self.assertIn("title", data, "No title in response")
        self.assertEqual(data["title"], "Test Conversation",
                         "Wrong title in response")

        # ネットワークが作成されたことを確認
        self.assertIn("network", data, "No network in response")
        self.assertIsNotNone(data["network"], "Network is None")

        return data["id"]

    def test_send_message(self):
        """メッセージ送信のテスト"""
        token = self.get_auth_token()
        conversation_id = self.test_create_conversation()

        # メッセージを送信
        response = requests.post(
            f"{API_URL}/chat/conversations/{conversation_id}/messages",
            json={"content": "Hello, world!"},
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 200, "Failed to send message")

        # レスポンスを検証
        data = response.json()
        self.assertIn("id", data, "No message ID in response")
        self.assertIn("content", data, "No content in response")
        self.assertEqual(data["content"], "Hello, world!",
                         "Wrong content in response")

        # メッセージリストを取得
        response = requests.get(
            f"{API_URL}/chat/conversations/{conversation_id}/messages",
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 200, "Failed to get messages")

        # レスポンスを検証
        data = response.json()
        self.assertIsInstance(data, list, "Response is not a list")
        self.assertGreaterEqual(len(data), 1, "No messages in response")

    def test_get_network_cytoscape(self):
        """ネットワークCytoscapeデータ取得のテスト"""
        token = self.get_auth_token()
        conversation_id = self.test_create_conversation()

        # 会話の詳細を取得してネットワークIDを取得
        response = requests.get(
            f"{API_URL}/chat/conversations/{conversation_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 200,
                         "Failed to get conversation")
        conversation = response.json()
        network_id = conversation["network"]["id"]

        # ネットワークCytoscapeデータを取得
        response = requests.get(
            f"{API_URL}/network/{network_id}/cytoscape",
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 200,
                         "Failed to get network cytoscape data")

        # レスポンスを検証
        data = response.json()
        self.assertIn("elements", data, "No elements in response")

    def test_proxy_endpoint(self):
        """プロキシエンドポイントのテスト"""
        token = self.get_auth_token()

        # プロキシエンドポイントを使用してNetworkXMCPサーバーの情報を取得
        response = requests.post(
            f"{API_URL}/proxy/networkx/tools/proxy_call",
            json={"arguments": {"endpoint": "health", "method": "GET"}},
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 200,
                         "Failed to use proxy endpoint")

        # レスポンスを検証
        data = response.json()
        self.assertIn("result", data, "No result in response")
        self.assertIn("status", data["result"], "No status in result")
        self.assertEqual(data["result"]["status"],
                         "ok", "Wrong status in result")

    def test_network_communication(self):
        """ネットワーク通信のテスト"""
        # このテストでは、フロントエンドからNetworkXMCPサーバーへの直接通信がないことを確認します
        # 実際のブラウザテストは難しいため、ここではAPIエンドポイントの確認のみを行います

        token = self.get_auth_token()

        # APIサーバーのプロキシエンドポイントを使用してNetworkXMCPサーバーにアクセス
        # proxy_callエンドポイントを使用して、NetworkXMCPサーバーのhealthエンドポイントにアクセス
        response = requests.post(
            f"{API_URL}/proxy/networkx/tools/proxy_call",
            json={"arguments": {"endpoint": "health", "method": "GET"}},
            headers={"Authorization": f"Bearer {token}"}
        )

        # エラーの詳細を出力
        if response.status_code != 200:
            print(f"Network communication response: {response.status_code}")
            print(f"Response content: {response.text}")

            # より詳細なエラー情報を取得
            try:
                error_details = response.json()
                print(f"Error details: {error_details}")
            except:
                print("Could not parse error details as JSON")

        self.assertEqual(response.status_code, 200,
                         "Failed to use proxy endpoint")

        # レスポンスを検証
        data = response.json()
        self.assertIn("result", data, "No result in response")
        self.assertIn("status", data["result"], "No status in result")
        self.assertEqual(data["result"]["status"], "ok", "Status is not ok")

    def test_upload_graphml_and_verify(self):
        """GraphMLファイルのアップロードと検証のテスト"""
        token = self.get_auth_token()

        # サンプルGraphMLファイルを開く
        file_path = os.path.join(os.path.dirname(
            __file__), 'fixed_random_graph_25_nodes.graphml')
        with open(file_path, 'rb') as f:
            files = {
                'file': ('fixed_random_graph_25_nodes.graphml', f, 'application/xml')}

            # /network/upload エンドポイントにファイルをアップロード
            response = requests.post(
                f"{API_URL}/network/upload",
                headers={"Authorization": f"Bearer {token}"},
                files=files
            )

        # レスポンスを検証
        self.assertEqual(response.status_code, 200,
                         f"Failed to upload GraphML file: {response.text}")
        data = response.json()
        self.assertIn("conversation_id", data)
        self.assertIn("network_id", data)

        network_id = data["network_id"]

        # アップロードされたネットワークがCytoscape形式で取得できるか確認
        response = requests.get(
            f"{API_URL}/network/{network_id}/cytoscape",
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 200,
                         f"Failed to get Cytoscape data: {response.text}")

        cyto_data = response.json()
        self.assertIn("elements", cyto_data)
        self.assertIn("nodes", cyto_data["elements"])
        self.assertIn("edges", cyto_data["elements"])
        self.assertGreater(
            len(cyto_data["elements"]["nodes"]), 0, "No nodes found in the uploaded graph")
        self.assertGreater(
            len(cyto_data["elements"]["edges"]), 0, "No edges found in the uploaded graph")


if __name__ == "__main__":
    unittest.main(verbosity=2)
