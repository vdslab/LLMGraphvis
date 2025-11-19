import requests
import sys
import uuid
import time

BASE_URL = "http://localhost:8000"

def verify_auth_robust():
    # Generate unique user
    username = f"user_{uuid.uuid4().hex[:8]}"
    password = "testpassword123"
    
    print(f"Testing Auth Flow for NEW user: {username}")
    
    # 1. Register
    print("\n1. Registering...")
    try:
        resp = requests.post(f"{BASE_URL}/auth/register", json={"username": username, "password": password})
        if resp.status_code == 200:
            print("   Success: Registered")
            data = resp.json()
            if "access_token" not in data:
                print("   Error: No access_token in register response")
                return False
        else:
            print(f"   Failed: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print(f"   Error: {e}")
        return False

    # 2. Login
    print("\n2. Logging in...")
    session = requests.Session()
    try:
        resp = session.post(f"{BASE_URL}/auth/token", data={"username": username, "password": password})
        if resp.status_code == 200:
            print("   Success: Logged in")
            print(f"   Cookies: {session.cookies.get_dict()}")
        else:
            print(f"   Failed: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print(f"   Error: {e}")
        return False
        
    # 3. Get Me (Protected)
    print("\n3. Accessing Protected Endpoint (/auth/users/me)...")
    try:
        resp = session.get(f"{BASE_URL}/auth/users/me")
        if resp.status_code == 200:
            user_data = resp.json()
            print(f"   Success: Retrieved user data: {user_data}")
            if user_data['username'] == username:
                print("   Verification Passed: Username matches.")
                return True
            else:
                print("   Verification Failed: Username mismatch.")
                return False
        else:
            print(f"   Failed: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print(f"   Error: {e}")
        return False

if __name__ == "__main__":
    if verify_auth_robust():
        print("\nRobust Auth Verification SUCCESS")
        sys.exit(0)
    else:
        print("\nRobust Auth Verification FAILED")
        sys.exit(1)
