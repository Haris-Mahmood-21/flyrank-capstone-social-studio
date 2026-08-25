"""
CLI script to create the initial admin user.

Usage:
    uv run python scripts/create_user.py --email admin@example.com --password secret
"""

import argparse
import asyncio
import sys

sys.path.insert(0, ".")

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models import User  # ensures all models are registered


async def create_user(email: str, password: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()
        if existing:
            print(f"User {email} already exists.")
            return
        user = User(email=email, hashed_password=hash_password(password))
        db.add(user)
        await db.commit()
        print(f"User created: {email}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create admin user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    asyncio.run(create_user(args.email, args.password))
