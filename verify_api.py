import requests
import sys

BASE_URL = "http://localhost:8000"

def test_register(username, password):
    print(f"Testing registration for {username}...")
    response = requests.post(f"{BASE_URL}/auth/register", json={"username": username, "password": password})
    if response.status_code == 200:
        print("Registration successful")
        return True
    elif response.status_code == 409:
        print("User already exists")
        return True
    else:
        print(f"Registration failed: {response.status_code} {response.text}")
        return False

def test_login(username, password):
    print(f"Testing login for {username}...")
    response = requests.post(f"{BASE_URL}/auth/token", data={"username": username, "password": password})
    if response.status_code == 200:
        print("Login successful")
        return response.json()["access_token"]
    else:
        print(f"Login failed: {response.status_code} {response.text}")
        return None

def test_create_chat(token):
    print("Testing chat creation...")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(f"{BASE_URL}/chat", json={"name": "Test Chat"}, headers=headers)
    if response.status_code == 200:
        print("Chat creation successful")
        return True
    else:
        print(f"Chat creation failed: {response.status_code} {response.text}")
        return False

def main():
    username = "testuser_api_verify"
    password = "testpassword123"

    if not test_register(username, password):
        sys.exit(1)
    
    token = test_login(username, password)
    if not token:
        sys.exit(1)
        
    if not test_create_chat(token):
        sys.exit(1)

    print("All backend tests passed!")

if __name__ == "__main__":
    main()
