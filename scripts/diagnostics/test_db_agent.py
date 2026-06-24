#!/usr/bin/env python3
"""
Test DB Agent initialization specifically
"""
import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

async def test_db_agent():
    """Test DB Agent initialization"""
    try:
        print("🚀 Testing DB Agent initialization...")
        
        # Import the DB Agent
        from app.agents.db_agent import DBAgent
        
        print("📊 Creating DB Agent instance...")
        db_agent = DBAgent()
        
        print("🔧 Initializing DB Agent...")
        await db_agent.initialize()
        
        print("✅ DB Agent initialized successfully!")
        
        print("🔍 Testing DB Agent capabilities...")
        capabilities = await db_agent.get_capabilities()
        print(f"📋 DB Agent capabilities: {capabilities}")
        
        print("🎉 DB Agent test successful!")
        
    except Exception as e:
        print(f"❌ DB Agent test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    print("🔧 Gabriel Agent - DB Agent Test")
    print("=" * 50)
    asyncio.run(test_db_agent())



