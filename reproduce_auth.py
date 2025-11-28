import requests
import sys
import uuid

BASE_URL = "http://localhost:8000"

def test_auth_flow():
    username = f"testuser_{uuid.uuid4().hex[:8]}"
    password = "testpassword123"
    
    print(f"Testing with username: {username}")
    
    # 1. Register
    print("\n--- Testing Registration ---")
    register_url = f"{BASE_URL}/auth/register"
    register_data = {
        "username": username,
        "password": password
    }
    
    try:
        response = requests.post(register_url, json=register_data)
        print(f"Register Status Code: {response.status_code}")
        if response.status_code != 200:
            print(f"Register Failed: {response.text}")
            return False
        
        print(f"Register Response: {response.json()}")
        cookies = response.cookies
        print(f"Cookies received: {cookies.get_dict()}")
        
        if "access_token" not in cookies:
            print("ERROR: access_token cookie not found in registration response")
        else:
            print("SUCCESS: access_token cookie found")
            
    except Exception as e:
        print(f"Exception during registration: {e}")
        return False

    # 2. Access Protected Endpoint (Auto-login check)
    print("\n--- Testing Auto-login (Access /auth/users/me) ---")
    me_url = f"{BASE_URL}/auth/users/me"
    try:
        response = requests.get(me_url, cookies=cookies)
        print(f"Me Status Code: {response.status_code}")
        if response.status_code != 200:
            print(f"Me Failed: {response.text}")
        else:
            print(f"Me Response: {response.json()}")
            print("SUCCESS: Auto-login worked")
            
    except Exception as e:
        print(f"Exception during auto-login check: {e}")

    # 3. Logout
    print("\n--- Testing Logout ---")
    logout_url = f"{BASE_URL}/auth/logout"
    try:
        response = requests.post(logout_url, cookies=cookies)
        print(f"Logout Status Code: {response.status_code}")
        if response.status_code != 200:
             print(f"Logout Failed: {response.text}")
        
        # Verify cookie is cleared (or expired)
        # Note: requests might not show it as cleared in the cookie jar immediately depending on how it handles expires
        # But subsequent requests should fail
        
    except Exception as e:
        print(f"Exception during logout: {e}")

    # 4. Login
    print("\n--- Testing Login ---")
    login_url = f"{BASE_URL}/auth/token"
    login_data = {
        "username": username,
        "password": password
    }
    
    try:
        # Note: OAuth2PasswordRequestForm expects form data, not JSON
        response = requests.post(login_url, data=login_data)
        print(f"Login Status Code: {response.status_code}")
        if response.status_code != 200:
            print(f"Login Failed: {response.text}")
            return False
            
        print(f"Login Response: {response.json()}")
        cookies = response.cookies
        print(f"Cookies received: {cookies.get_dict()}")
        
        if "access_token" not in cookies:
            print("ERROR: access_token cookie not found in login response")
        else:
            print("SUCCESS: access_token cookie found")
            
    except Exception as e:
        print(f"Exception during login: {e}")
        return False

    # 5. Access Protected Endpoint (Login check)
    print("\n--- Testing Login Access (Access /auth/users/me) ---")
    try:
        response = requests.get(me_url, cookies=cookies)
        print(f"Me Status Code: {response.status_code}")
        if response.status_code != 200:
            print(f"Me Failed: {response.text}")
            return False
        else:
            print(f"Me Response: {response.json()}")
            print("SUCCESS: Login access worked")
            
    except Exception as e:
        print(f"Exception during login access check: {e}")
        return False

    return True

if __name__ == "__main__":
    if test_auth_flow():
        print("\nOverall Test Result: PASSED")
        sys.exit(0)
    else:
        print("\nOverall Test Result: FAILED")
        sys.exit(1)
