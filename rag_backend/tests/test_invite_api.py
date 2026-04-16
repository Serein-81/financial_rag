import asyncio
import requests
from sqlalchemy import text
from app.db.session import engine
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

async def test_api():
    async with engine.begin() as conn:
        result = await conn.execute(text('SELECT id, email, is_admin, tenant_id FROM users LIMIT 1'))
        row = result.fetchone()
        if row:
            print(f"User: {row}")
            user_id, email, is_admin, tenant_id = row
            print(f"is_admin: {is_admin}, tenant_id: {tenant_id}")

asyncio.run(test_api())

token_response = requests.post(
    'http://localhost:8000/api/v1/auth/login',
    json={"email": "admin@example.com", "password": "admin123"}
)

if token_response.status_code == 200:
    token = token_response.json()['access_token']
    print(f"\nGot token: {token[:20]}...")

    headers = {'Authorization': f'Bearer {token}'}

    response = requests.get(
        'http://localhost:8000/api/v1/invite-codes',
        headers=headers
    )

    print(f"\nStatus code: {response.status_code}")
    print(f"Response: {response.text[:500]}")
else:
    print(f"Login failed: {token_response.status_code} - {token_response.text}")
