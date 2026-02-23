#!/usr/bin/env python3
"""
Working Database Cleanup Script
Uses the existing Gabriel Agent API with proper error handling.
"""

import requests
import json
import os
from pathlib import Path

# Configuration
API_BASE_URL = "https://gabriel-agent-709613591310.us-east1.run.app"
LOCAL_FAISS_DIR = "faiss_db"

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
    
    return counts

def clear_sql_tables():
    """Clear SQL tables using the API."""
    print("\nClearing SQL Database...")
    
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
    failed_tables = []
    
    for table in tables_to_clear:
        try:
            print(f"  Clearing table: {table}")
            
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
                    print(f"    API Error: {data.get('message', 'Unknown error')}")
                    failed_tables.append(table)
            else:
                print(f"    HTTP Error {response.status_code}: {response.text}")
                failed_tables.append(table)
                
        except Exception as e:
            print(f"    Exception: {e}")
            failed_tables.append(table)
    
    return cleared_tables, failed_tables

def clear_vector_database():
    """Clear vector database files."""
    print("\nClearing Vector Database...")
    
    cleared_files = []
    
    # Clear local FAISS files
    faiss_dir = Path(LOCAL_FAISS_DIR)
    if faiss_dir.exists():
        faiss_files = list(faiss_dir.glob("*.faiss")) + list(faiss_dir.glob("*.pkl"))
        
        for file_path in faiss_files:
            try:
                file_path.unlink()
                print(f"  Deleted local file: {file_path.name}")
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
        print(f"  Local FAISS directory {faiss_dir} does not exist")
    
    # Try to clear via STORAGE_AGENT API
    try:
        print("  Attempting to clear via STORAGE_AGENT...")
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

def main():
    """Main cleanup function."""
    print("Gabriel Agent Database Cleanup (Working Version)")
    print("=" * 55)
    
    # Test API connection first
    if not test_api_connection():
        print("Cannot proceed without API connection")
        return
    
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
    initial_counts = get_database_counts()
    
    # Clear SQL tables
    print("\n2. Clearing SQL Database...")
    cleared_tables, failed_tables = clear_sql_tables()
    
    if cleared_tables:
        print(f"   Successfully cleared {len(cleared_tables)} tables: {', '.join(cleared_tables)}")
    if failed_tables:
        print(f"   Failed to clear {len(failed_tables)} tables: {', '.join(failed_tables)}")
    
    # Clear vector database
    print("\n3. Clearing Vector Database...")
    cleared_files = clear_vector_database()
    print(f"   Cleared {len(cleared_files)} local vector files")
    
    # Get final counts
    print("\n4. Getting final database state...")
    final_counts = get_database_counts()
    
    # Summary
    print("\n" + "=" * 55)
    print("CLEANUP SUMMARY")
    print("=" * 55)
    
    print(f"SQL Tables cleared: {len(cleared_tables)}/{len(cleared_tables) + len(failed_tables)}")
    print(f"Vector files cleared: {len(cleared_files)}")
    
    if initial_counts.get('entities') != "Error" and final_counts.get('entities') != "Error":
        print(f"Entity count: {initial_counts.get('entities', 'Unknown')} → {final_counts.get('entities', 'Unknown')}")
    
    if initial_counts.get('documents') != "Error" and final_counts.get('documents') != "Error":
        print(f"Document count: {initial_counts.get('documents', 'Unknown')} → {final_counts.get('documents', 'Unknown')}")
    
    if failed_tables:
        print(f"\nSome SQL tables failed to clear: {', '.join(failed_tables)}")
        print("   You may need to clear these manually or check database permissions.")
    else:
        print("\nAll cleanup operations completed successfully!")

if __name__ == "__main__":
    main()
