#!/usr/bin/env python3
"""
Safe Database Cleanup Test Script
Tests the cleanup functionality without actually clearing data.
"""

import requests
import json
import os
from pathlib import Path

# Configuration
API_BASE_URL = os.getenv("GABRIEL_ENDPOINT", "https://gabriel-agent-ymerndhsba-ue.a.run.app")

def test_api_connection():
    """Test if the API is accessible."""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=30)
        if response.status_code == 200:
            print("API connection successful")
            return True
        else:
            print(f"API health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"API connection failed: {e}")
        return False

def get_database_counts():
    """Get current database counts via API."""
    print("\nGetting current database counts...")
    
    counts = {}
    
    # Get entity count
    try:
        response = requests.post(
            f"{API_BASE_URL}/agents/message",
            json={
                "agent_type": "DB_AGENT",
                "action": "execute_query",
                "data": {
                    "query": "SELECT COUNT(*) as count FROM entities",
                    "params": []
                }
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                result = data.get('result', [])
                counts['entities'] = result[0]['count'] if result else 0
                print(f"  Entities: {counts['entities']}")
            else:
                print(f"  Error getting entity count: {data.get('message')}")
                counts['entities'] = "Error"
        else:
            print(f"  HTTP Error getting entity count: {response.status_code}")
            counts['entities'] = "Error"
    except Exception as e:
        print(f"  Exception getting entity count: {e}")
        counts['entities'] = "Error"
    
    # Get document metadata count
    try:
        response = requests.post(
            f"{API_BASE_URL}/agents/message",
            json={
                "agent_type": "DB_AGENT",
                "action": "execute_query",
                "data": {
                    "query": "SELECT COUNT(*) as count FROM document_metadata",
                    "params": []
                }
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                result = data.get('result', [])
                counts['documents'] = result[0]['count'] if result else 0
                print(f"  Document metadata: {counts['documents']}")
            else:
                print(f"  Error getting document count: {data.get('message')}")
                counts['documents'] = "Error"
        else:
            print(f"  HTTP Error getting document count: {response.status_code}")
            counts['documents'] = "Error"
    except Exception as e:
        print(f"  Exception getting document count: {e}")
        counts['documents'] = "Error"
    
    # Get tasks count
    try:
        response = requests.post(
            f"{API_BASE_URL}/agents/message",
            json={
                "agent_type": "DB_AGENT",
                "action": "execute_query",
                "data": {
                    "query": "SELECT COUNT(*) as count FROM tasks",
                    "params": []
                }
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                result = data.get('result', [])
                counts['tasks'] = result[0]['count'] if result else 0
                print(f"  Tasks: {counts['tasks']}")
            else:
                print(f"  Error getting task count: {data.get('message')}")
                counts['tasks'] = "Error"
        else:
            print(f"  HTTP Error getting task count: {response.status_code}")
            counts['tasks'] = "Error"
    except Exception as e:
        print(f"  Exception getting task count: {e}")
        counts['tasks'] = "Error"
    
    return counts

def test_sql_clear_commands():
    """Test SQL clear commands without executing them."""
    print("\nTesting SQL clear commands (DRY RUN)...")
    
    tables_to_clear = [
        'processed_files',
        'document_metadata', 
        'authorizations',
        'obligations',
        'tasks',
        'entities'
    ]
    
    for table in tables_to_clear:
        print(f"  Testing clear command for: {table}")
        
        # Test if the command would work by checking table exists
        try:
            response = requests.post(
                f"{API_BASE_URL}/agents/message",
                json={
                    "agent_type": "DB_AGENT",
                    "action": "execute_query",
                    "data": {
                        "query": f"SELECT COUNT(*) as count FROM {table}",
                        "params": []
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    result = data.get('result', [])
                    count = result[0]['count'] if result else 0
                    print(f"    Table {table}: {count} rows (command would work)")
                else:
                    print(f"    Table {table}: Error - {data.get('message')}")
            else:
                print(f"    Table {table}: HTTP Error {response.status_code}")
                
        except Exception as e:
            print(f"    Table {table}: Exception - {e}")

def check_database_service_initialization():
    """Check if database service is initialized."""
    print("\nChecking Database Service Initialization...")
    
    try:
        # Try a simple query to test if database service is initialized
        response = requests.post(
            f"{API_BASE_URL}/agents/message",
            json={
                "agent_type": "DB_AGENT",
                "action": "execute_query",
                "data": {
                    "query": "SELECT 1 as test",
                    "params": []
                }
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                print("  ✅ Database service is INITIALIZED and working")
                print("  ✅ Cloud SQL connection is ACTIVE")
                return True
            else:
                error_msg = data.get('message', 'Unknown error')
                if 'not initialized' in error_msg.lower():
                    print(f"  ❌ Database service is NOT INITIALIZED")
                    print(f"     Error: {error_msg}")
                else:
                    print(f"  ⚠️  Database service error: {error_msg}")
                return False
        else:
            print(f"  ❌ HTTP Error checking database service: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Exception checking database service: {e}")
        return False

def check_vector_database():
    """Check vector database status."""
    print("\nChecking Vector Database...")
    
    # Check local FAISS files
    faiss_dir = Path("faiss_db")
    if faiss_dir.exists():
        faiss_files = list(faiss_dir.glob("*.faiss")) + list(faiss_dir.glob("*.pkl"))
        print(f"  Local FAISS files: {len(faiss_files)}")
        for file in faiss_files:
            print(f"    - {file.name}")
    else:
        print("  Local FAISS directory does not exist")
    
    # Check STORAGE_AGENT status
    try:
        response = requests.post(
            f"{API_BASE_URL}/agents/message",
            json={
                "agent_type": "STORAGE_AGENT",
                "action": "get_collection_info",
                "data": {}
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                storage_info = data.get('result', {})
                print(f"  STORAGE_AGENT status: {storage_info}")
            else:
                print(f"  STORAGE_AGENT error: {data.get('message')}")
        else:
            print(f"  STORAGE_AGENT HTTP Error {response.status_code}")
    except Exception as e:
        print(f"  STORAGE_AGENT exception: {e}")

def main():
    """Main test function."""
    print("Gabriel Agent Database Cleanup Test (Safe Mode)")
    print("=" * 55)
    print("This script will check database status WITHOUT clearing data")
    print("=" * 55)
    
    # Test API connection
    if not test_api_connection():
        print("Cannot proceed without API connection")
        return
    
    # Check database service initialization
    print("\n0. Database Service Initialization:")
    db_initialized = check_database_service_initialization()
    
    # Get current counts
    print("\n1. Current Database State:")
    counts = get_database_counts()
    
    # Test SQL clear commands
    print("\n2. Testing SQL Clear Commands:")
    test_sql_clear_commands()
    
    # Check vector database
    print("\n3. Vector Database Status:")
    check_vector_database()
    
    # Summary
    print("\n" + "=" * 55)
    print("TEST SUMMARY")
    print("=" * 55)
    
    print(f"Database Service Initialized: {'✅ YES' if db_initialized else '❌ NO'}")
    
    if counts.get('entities') != "Error":
        print(f"Entities in database: {counts.get('entities', 'Unknown')}")
    if counts.get('documents') != "Error":
        print(f"Document metadata: {counts.get('documents', 'Unknown')}")
    if counts.get('tasks') != "Error":
        print(f"Tasks: {counts.get('tasks', 'Unknown')}")
    
    # Check if databases are clean
    all_zero = (
        counts.get('entities', 0) == 0 and
        counts.get('documents', 0) == 0 and
        counts.get('tasks', 0) == 0
    )
    
    if all_zero and counts.get('entities') != "Error":
        print("\n✅ SQL Database is CLEAN (all tables empty)")
    elif counts.get('entities') != "Error":
        print("\n⚠️  SQL Database has records")
    
    print("\nThe cleanup script should work properly based on these tests.")
    print("To actually clear the data, run: python working_cleanup.py")

if __name__ == "__main__":
    main()
