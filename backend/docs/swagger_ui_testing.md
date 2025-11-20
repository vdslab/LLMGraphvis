# GraphVisAgent API Testing with Swagger UI

This document provides instructions for testing the GraphVisAgent API using Swagger UI with authentication.

## Overview

The GraphVisAgent API uses JWT-based authentication and supports two authentication methods:

1. **Cookie-based authentication**: Used by the frontend application
2. **Bearer token authentication**: Used for API testing via Swagger UI or other API clients

## Public vs Protected Endpoints

The following endpoints are public and do not require authentication:

- `GET /health` - Health check endpoint
- `POST /auth/register` - Register a new user
- `POST /auth/token` - Login to obtain an access token

All other endpoints require authentication.

## Accessing Swagger UI

1. Start the backend server:
   ```bash
   cd backend
   uvicorn app.main:app --reload
   ```
2. Navigate to: `http://localhost:8000/docs`

## Authentication Process

### Step 1: Obtain an Authentication Token

1. In the Swagger UI, locate and expand the `/auth/token` endpoint (login endpoint)
2. Click the "Try it out" button
3. Enter your credentials using the form fields:
   - **username**: your_username
   - **password**: your_password
   - (You don't need to modify the request body as it will be automatically populated)
4. Click "Execute"
5. If successful, you will receive a response that includes an `access_token`
6. Copy the value of `access_token` (without quotes)

### Step 2: Authorize in Swagger UI

1. Click the "Authorize" button at the top right of the Swagger UI
2. In the authorization popup:
   - Enter your token in the OAuth2PasswordBearer field (no need to add "Bearer" prefix)
3. Click "Authorize" and then "Close"

You are now authenticated! The authorization will persist across page refreshes thanks to the `persistAuthorization: true` setting.

### Testing the Authentication

After authorizing, you can verify your authentication is working by using the `/auth/users/me` endpoint:

1. Expand the `GET /auth/users/me` endpoint
2. Click "Try it out"
3. Click "Execute"
4. You should receive your user information if authentication is successful

## Testing Protected Endpoints

Once authorized, you can test any protected endpoint:

1. Expand the endpoint you want to test (e.g., `/chat` to list all chats)
2. Click "Try it out"
3. Fill in any required parameters
4. Click "Execute"
5. Review the response

The Swagger UI will automatically include your authorization token in all requests.

## Common Issues and Solutions

### 401 Unauthorized Error

If you receive a 401 error:
- Check that your token is valid and hasn't expired
- Verify that you've properly authorized in Swagger UI
- Try logging in again to obtain a fresh token
- Make sure you're not trying to access an endpoint with insufficient permissions

### Token Expiration

Tokens expire after 30 minutes by default. If your token expires:
1. Use the `/auth/token` endpoint again to obtain a new token
2. Re-authorize with the new token

### Registration First

If you don't have a user account yet:
1. Use the `/auth/register` endpoint to create a new account
2. Then use the `/auth/token` endpoint to log in

## Using Authentication in External Tools

To use these APIs outside of Swagger UI (e.g., Postman, curl):

### curl Example:
```bash
# Register a new user
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpassword"}'

# Get token (OAuth2 password flow)
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=testpassword"

# Use token (replace YOUR_TOKEN with the actual token)
curl http://localhost:8000/chat \
  -H "Authorization: Bearer YOUR_TOKEN"

# Test authentication with /users/me endpoint
curl http://localhost:8000/auth/users/me \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Postman:
1. Set the request Authorization type to "Bearer Token"
2. Enter your token value
3. Send your request

## Browser and API Clients

Our authentication system supports both browser clients and API clients:

1. **Browser Clients**: When logging in via the frontend, the server sets an HTTP-only cookie containing the token. All subsequent requests from the browser will include this cookie automatically.

2. **API Clients/Swagger UI**: These clients use the Bearer token in the Authorization header.

Both methods are fully supported and will work interchangeably.

## Security Notes

- The server uses Argon2 for password hashing, which is a secure and modern hashing algorithm
- JWT tokens are signed using HS256 (HMAC with SHA-256) to prevent tampering
- Tokens expire after 30 minutes for security reasons