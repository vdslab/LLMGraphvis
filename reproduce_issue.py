import httpx
import asyncio

BASE_URL = "http://localhost:8000"

async def check_health():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/health")
            print(f"Health Check: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Health Check Failed: {e}")

async def register_user():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/auth/register",
                json={"username": "testuser", "password": "password123"}
            )
            print(f"Register: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Register Failed: {e}")

async def main():
    await check_health()
    await register_user()

if __name__ == "__main__":
    asyncio.run(main())
