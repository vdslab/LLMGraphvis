import requests
import sys

BASE_URL = "http://localhost:8000"

def test_register_autologin(username, password):
    print(f"Testing registration for {username}...")
    session = requests.Session()
    response = session.post(f"{BASE_URL}/auth/register", json={"username": username, "password": password})
    
    if response.status_code == 200:
        print("Registration successful")
        
        # Check if cookie is set in the session
        cookies = session.cookies.get_dict()
        print(f"Cookies received: {cookies}")
        
        if "access_token" in cookies:
            print("SUCCESS: access_token cookie found in registration response.")
            
            # Verify we can access protected endpoint with this cookie
            print("Verifying access to /auth/users/me with cookie...")
            me_response = session.get(f"{BASE_URL}/auth/users/me")
            if me_response.status_code == 200:
                print("SUCCESS: Successfully accessed protected endpoint.")
                return True
            else:
                print(f"FAILURE: Failed to access protected endpoint. Status: {me_response.status_code}")
                return False
        else:
            print("FAILURE: access_token cookie NOT found in registration response.")
            return False
    else:
        print(f"Registration failed: {response.status_code} {response.text}")
        return False

def main():
    username = "autologin_test_user"
    password = "password123"
    
    if test_register_autologin(username, password):
        print("Backend auto-login verification passed!")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
