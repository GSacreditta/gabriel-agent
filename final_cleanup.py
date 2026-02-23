#!/usr/bin/env python3
"""
Final Database Cleanup Script
Clears what we can access: Vector database and local files.
SQL database appears to be inaccessible via API.
"""

import requests
import json
import os
from pathlib import Path

# Configuration
API_BASE_URL = "https://gabriel-agent-709613591310.us-east1.run.app"

def test_api_connection():
    """Test if the API is accessible."""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            print("API connection successful")
            return True
        else:
            print(f"API health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"API connection failed: {e}")
        return False

def clear_vector_database():
    """Clear vector database files and cloud storage."""
    print("\nClearing Vector Database...")
    
    cleared_files = []
    
    # Clear local FAISS files
    faiss_dirs = ["faiss_db", "chroma_db", "test_chroma_db"]
    
    for faiss_dir in faiss_dirs:
        path = Path(faiss_dir)
        if path.exists():
            print(f"  Found local directory: {path}")
            faiss_files = list(path.glob("*.faiss")) + list(path.glob("*.pkl")) + list(path.glob("*.db"))
            
            for file_path in faiss_files:
                try:
                    file_path.unlink()
                    print(f"    Deleted: {file_path.name}")
                    cleared_files.append(str(file_path))
                except Exception as e:
                    print(f"    Error deleting {file_path.name}: {e}")
            
            # Remove directory if empty
            try:
                if not any(path.iterdir()):
                    path.rmdir()
                    print(f"    Removed empty directory: {path}")
            except Exception as e:
                print(f"    Could not remove directory: {e}")
        else:
            print(f"  Directory not found: {faiss_dir}")
    
    # Try to clear via STORAGE_AGENT API
    try:
        print("  Attempting to clear via STORAGE_AGENT...")
        
        # Try collection maintenance
        response = requests.post(
            f"{API_BASE_URL}/agents/message",
            json={
                "agent_type": "STORAGE_AGENT",
                "action": "collection_maintenance",
                "data": {}
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                print("    STORAGE_AGENT maintenance completed")
            else:
                print(f"    STORAGE_AGENT warning: {data.get('message')}")
        else:
            print(f"    STORAGE_AGENT HTTP Error {response.status_code}")
    except Exception as e:
        print(f"    STORAGE_AGENT exception: {e}")
    
    return cleared_files

def check_sql_database_status():
    """Check if SQL database is accessible."""
    print("\nChecking SQL Database Status...")
    
    try:
        # Try to get entity count
        response = requests.post(
            f"{API_BASE_URL}/agents/message",
            json={
                "agent_type": "DB_AGENT",
                "action": "list_entities",
                "data": {}
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                entities = data.get('result', [])
                print(f"  SQL Database accessible: {len(entities)} entities found")
                return True
            else:
                print(f"  SQL Database error: {data.get('message')}")
                return False
        else:
            print(f"  SQL Database HTTP Error: {response.status_code}")
            return False
    except Exception as e:
        print(f"  SQL Database exception: {e}")
        return False

def clear_sql_database_manual():
    """Provide manual SQL commands for clearing database."""
    print("\nSQL Database Manual Clear Commands:")
    print("=" * 50)
    print("The SQL database is not accessible via API.")
    print("You can clear it manually using these SQL commands:")
    print()
    print("-- Connect to your PostgreSQL database and run:")
    print("TRUNCATE TABLE processed_files CASCADE;")
    print("TRUNCATE TABLE document_metadata CASCADE;")
    print("TRUNCATE TABLE authorizations CASCADE;")
    print("TRUNCATE TABLE obligations CASCADE;")
    print("TRUNCATE TABLE tasks CASCADE;")
    print("TRUNCATE TABLE entities CASCADE;")
    print()
    print("-- Or use this single command to clear all tables:")
    print("TRUNCATE TABLE processed_files, document_metadata, authorizations, obligations, tasks, entities CASCADE;")
    print("=" * 50)

def main():
    """Main cleanup function."""
    print("Gabriel Agent Database Cleanup (Final Version)")
    print("=" * 55)
    
    # Test API connection
    if not test_api_connection():
        print("Cannot proceed without API connection")
        return
    
    # Check SQL database status
    sql_accessible = check_sql_database_status()
    
    # Clear vector database
    print("\n1. Clearing Vector Database...")
    cleared_files = clear_vector_database()
    print(f"   Cleared {len(cleared_files)} local vector files")
    
    # Handle SQL database
    if sql_accessible:
        print("\n2. SQL Database is accessible via API")
        print("   You can use the working_cleanup.py script to clear SQL tables")
    else:
        print("\n2. SQL Database is NOT accessible via API")
        clear_sql_database_manual()
    
    # Summary
    print("\n" + "=" * 55)
    print("CLEANUP SUMMARY")
    print("=" * 55)
    
    print(f"Vector files cleared: {len(cleared_files)}")
    
    if sql_accessible:
        print("SQL Database: Accessible via API (use working_cleanup.py)")
    else:
        print("SQL Database: Requires manual clearing (see commands above)")
    
    print("\nVector database cleanup completed!")
    if not sql_accessible:
        print("For SQL database, use the manual commands provided above.")

if __name__ == "__main__":
    main()
