#!/usr/bin/env python3
"""
Database Cleanup via API
Uses the existing Gabriel Agent API endpoints to clear databases.
This approach avoids direct database connection issues.
"""

import requests
import json
import os
from pathlib import Path

# Configuration
API_BASE_URL = "https://gabriel-agent-709613591310.us-east1.run.app"
LOCAL_FAISS_DIR = "faiss_db"  # Local FAISS directory

def clear_sql_tables_via_api():
    """Clear SQL tables using the API endpoints."""
    print("Clearing SQL Database via API...")
    
    # Tables to clear in dependency order
    tables_to_clear = [
        'processed_files',
        'document_metadata', 
        'authorizations',
        'obligations',
        'tasks',
        'entities'
    ]
    
    cleared_tables = []
    
    for table in tables_to_clear:
        try:
            print(f"  Clearing table: {table}")
            
            # Use the agents/message endpoint to clear each table
            response = requests.post(
                f"{API_BASE_URL}/agents/message",
                json={
                    "agent_type": "DB_AGENT",
                    "action": "execute_command",
                    "data": {
                        "query": f"TRUNCATE TABLE {table} CASCADE",
                        "params": []
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    rows_affected = data.get('result', 0)
                    print(f"    Success: {rows_affected} rows cleared")
                    cleared_tables.append(table)
                else:
                    print(f"    Error: {data.get('message', 'Unknown error')}")
            else:
                print(f"    HTTP Error {response.status_code}: {response.text}")
                
        except Exception as e:
            print(f"    Exception: {e}")
    
    return cleared_tables

def clear_vector_database_local():
    """Clear local FAISS vector database files."""
    print("Clearing Vector Database (local files)...")
    
    faiss_dir = Path(LOCAL_FAISS_DIR)
    cleared_files = []
    
    if faiss_dir.exists():
        # Find and delete FAISS files
        faiss_files = list(faiss_dir.glob("*.faiss")) + list(faiss_dir.glob("*.pkl"))
        
        for file_path in faiss_files:
            try:
                file_path.unlink()
                print(f"  Deleted: {file_path.name}")
                cleared_files.append(str(file_path))
            except Exception as e:
                print(f"  Error deleting {file_path.name}: {e}")
        
        # Remove directory if empty
        try:
            if not any(faiss_dir.iterdir()):
                faiss_dir.rmdir()
                print(f"  Removed empty directory: {faiss_dir}")
        except Exception as e:
            print(f"  Could not remove directory: {e}")
    else:
        print(f"  Directory {faiss_dir} does not exist")
    
    return cleared_files

def clear_vector_database_via_api():
    """Clear vector database using API endpoints."""
    print("Clearing Vector Database via API...")
    
    try:
        # Try to clear vector database via STORAGE_AGENT
        response = requests.post(
            f"{API_BASE_URL}/agents/message",
            json={
                "agent_type": "STORAGE_AGENT",
                "action": "clear_all_vectors",
                "data": {}
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                print("  Success: Vector database cleared via API")
                return True
            else:
                print(f"  API Error: {data.get('message', 'Unknown error')}")
        else:
            print(f"  HTTP Error {response.status_code}: {response.text}")
            
    except Exception as e:
        print(f"  Exception: {e}")
    
    return False

def get_current_counts():
    """Get current database counts via API."""
    print("Getting current database counts...")
    
    try:
        # Get entity count
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
                entity_count = result[0]['count'] if result else 0
                print(f"  Entities: {entity_count}")
            else:
                print(f"  Error getting entity count: {data.get('message')}")
        else:
            print(f"  HTTP Error getting counts: {response.status_code}")
            
    except Exception as e:
        print(f"  Exception getting counts: {e}")

def main():
    """Main cleanup function."""
    print("Gabriel Agent Database Cleanup (via API)")
    print("=" * 50)
    
    # Confirm action
    print("\nWARNING: This will permanently delete ALL data from:")
    print("   - SQL Database (entities, tasks, obligations, authorizations, document_metadata, processed_files)")
    print("   - FAISS Vector Database (all document embeddings)")
    print("\nThis action cannot be undone!")
    
    response = input("\nAre you sure you want to proceed? (type 'YES' to confirm): ")
    if response != 'YES':
        print("Cleanup cancelled by user")
        return
    
    print("\nStarting cleanup...")
    
    # Get initial counts
    print("\n1. Getting initial database state...")
    get_current_counts()
    
    # Clear SQL tables
    print("\n2. Clearing SQL Database...")
    cleared_tables = clear_sql_tables_via_api()
    print(f"   Cleared {len(cleared_tables)} tables: {', '.join(cleared_tables)}")
    
    # Clear vector database
    print("\n3. Clearing Vector Database...")
    
    # Try API first
    api_success = clear_vector_database_via_api()
    
    # Also clear local files
    cleared_files = clear_vector_database_local()
    print(f"   Cleared {len(cleared_files)} local files")
    
    # Get final counts
    print("\n4. Getting final database state...")
    get_current_counts()
    
    print("\n" + "=" * 50)
    print("CLEANUP COMPLETE!")
    print("=" * 50)
    
    if cleared_tables and (api_success or cleared_files):
        print("Both SQL and Vector databases have been cleared")
    else:
        print("Some cleanup operations may have failed - check output above")

if __name__ == "__main__":
    main()
