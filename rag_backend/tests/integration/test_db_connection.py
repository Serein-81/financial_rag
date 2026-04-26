"""
Simple database connection test
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.db.session import AsyncSessionLocal


async def test_simple_query():
    """Test simple database connection"""
    print("=" * 60)
    print("Testing database connection...")
    print("=" * 60)
    
    try:
        async with AsyncSessionLocal() as session:
            print(f"Session created: {session}")
            print(f"Session ID: {id(session)}")
            
            # Test 1: Simple query
            print("\n[Test 1] Executing simple query...")
            result = await session.execute(text("SELECT 1 as test"))
            row = result.scalar()
            print(f"[OK] Query result: {row}")
            
            # Test 2: Check tables exist
            print("\n[Test 2] Checking user_financial_data table...")
            result = await session.execute(
                text("SELECT COUNT(*) FROM user_financial_data WHERE tenant_id = 'default'")
            )
            count = result.scalar()
            print(f"[OK] Found {count} records for tenant 'default'")
            
            # Test 3: Check other tables
            print("\n[Test 3] Checking system tables...")
            result = await session.execute(
                text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name LIKE '%financial%'
                """)
            )
            tables = [row[0] for row in result.fetchall()]
            print(f"[OK] Financial tables found: {tables}")
            
            print("\n" + "=" * 60)
            print("All database tests passed!")
            print("=" * 60)
            return True
            
    except Exception as e:
        print(f"\n[FAIL] Database test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_simple_query())
    sys.exit(0 if success else 1)
