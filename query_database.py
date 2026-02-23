#!/usr/bin/env python3
"""
Query PostgreSQL Database - Check Entity table and document metadata
"""

import requests
import json

def query_entities():
    """Query the Entity table via DB_AGENT"""
    try:
        print("=== QUERYING ENTITY TABLE ===")
        
        # Use the agents/message endpoint to query DB_AGENT
        response = requests.post(
            "https://gabriel-agent-709613591310.us-east1.run.app/agents/message",
            json={
                "agent_type": "DB_AGENT",
                "action": "list_entities",
                "data": {}
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"Status: {data.get('status')}")
            
            if data.get('status') == 'success':
                entities = data.get('result', [])
                print(f"Found {len(entities)} entities in database:")
                
                for entity in entities:
                    print(f"  - {entity.get('name', 'Unknown')} (ID: {entity.get('entity_id', 'N/A')})")
                    print(f"    Category: {entity.get('category', 'N/A')}")
                    print(f"    Created: {entity.get('created_at', 'N/A')}")
                    print()
                
                return entities
            else:
                print(f"DB_AGENT error: {data.get('message', 'Unknown error')}")
                return []
        else:
            print(f"HTTP Error {response.status_code}: {response.text}")
            return []
            
    except Exception as e:
        print(f"Error querying entities: {e}")
        return []

def check_strobe_entity():
    """Check specifically for Strobe entity"""
    try:
        print("=== CHECKING FOR STROBE ENTITY ===")
        
        response = requests.post(
            "https://gabriel-agent-709613591310.us-east1.run.app/agents/message",
            json={
                "agent_type": "DB_AGENT",
                "action": "match_entity",
                "data": {"name": "Strobe"}
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"Status: {data.get('status')}")
            
            if data.get('status') == 'success':
                entity = data.get('result')
                if entity:
                    print("✅ Strobe entity FOUND in database:")
                    print(f"  Name: {entity.get('name')}")
                    print(f"  ID: {entity.get('entity_id')}")
                    print(f"  Category: {entity.get('category')}")
                    return True
                else:
                    print("❌ Strobe entity NOT found in database")
                    return False
            else:
                print(f"DB_AGENT error: {data.get('message')}")
                return False
        else:
            print(f"HTTP Error {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        print(f"Error checking Strobe entity: {e}")
        return False

def check_document_metadata():
    """Check if there's any document metadata stored"""
    try:
        print("=== CHECKING DOCUMENT METADATA ===")
        
        # Try to get document metadata from database
        response = requests.post(
            "https://gabriel-agent-709613591310.us-east1.run.app/agents/message",
            json={
                "agent_type": "DB_AGENT",
                "action": "execute_query",
                "data": {
                    "query": "SELECT * FROM document_metadata LIMIT 10",
                    "params": []
                }
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"Status: {data.get('status')}")
            
            if data.get('status') == 'success':
                rows = data.get('result', [])
                print(f"Found {len(rows)} document metadata records")
                
                for row in rows[:5]:  # Show first 5
                    print(f"  - Document: {row[1] if len(row) > 1 else 'Unknown'}")  # Assuming file_name is second column
                    print(f"    Entity: {row[2] if len(row) > 2 else 'Unknown'}")    # Assuming entity_id is third column
                
                return len(rows) > 0
            else:
                print(f"Query error: {data.get('message')}")
                return False
        else:
            print(f"HTTP Error {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        print(f"Error checking document metadata: {e}")
        return False

if __name__ == "__main__":
    print("Querying PostgreSQL Database...")
    print("=" * 50)
    
    # Check entities
    entities = query_entities()
    
    # Check specifically for Strobe
    strobe_exists = check_strobe_entity()
    
    # Check document metadata
    docs_exist = check_document_metadata()
    
    print("=" * 50)
    print("ANALYSIS:")
    
    if not entities:
        print("🚨 NO ENTITIES in database - this explains why HDL approval is always triggered")
    else:
        print(f"✅ {len(entities)} entities found in database")
        
        if strobe_exists:
            print("✅ Strobe entity exists - should skip HDL approval and process directly")
        else:
            print("❌ Strobe entity missing - will trigger HDL approval")
    
    if docs_exist:
        print("✅ Document metadata exists - some processing has occurred")
    else:
        print("❌ No document metadata - processing pipeline not completing")
