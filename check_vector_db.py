#!/usr/bin/env python3
"""
Check Vector Database Contents
"""

import requests
import json

def search_vector_db():
    """Search the vector database to see what documents are stored"""
    
    try:
        # Search for general documents
        response = requests.post(
            "https://gabriel-agent-709613591310.us-east1.run.app/faiss/search?query=documents&top_k=10",
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print("=== VECTOR DATABASE SEARCH RESULTS ===")
            print(f"Status: {data.get('status', 'unknown')}")
            
            if data.get('documents'):
                print(f"\nFound {len(data['documents'])} documents:")
                for i, doc in enumerate(data['documents']):
                    metadata = doc.get('metadata', {})
                    content_preview = doc.get('content', '')[:100] + "..." if len(doc.get('content', '')) > 100 else doc.get('content', '')
                    
                    print(f"\n{i+1}. {metadata.get('file_name', 'Unknown')}")
                    print(f"   Type: {metadata.get('document_type', 'Unknown')}")
                    print(f"   Entity: {metadata.get('entity_name', 'Unknown')}")
                    print(f"   Content: {content_preview}")
            else:
                print("\nNo documents found in vector database")
                
        else:
            print(f"Error: HTTP {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"Error searching vector database: {e}")

def search_strobe_specifically():
    """Search specifically for Strobe documents"""
    
    try:
        response = requests.post(
            "https://gabriel-agent-709613591310.us-east1.run.app/faiss/search?query=Strobe Q1 2025&top_k=5",
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print("\n=== STROBE Q1 2025 SEARCH RESULTS ===")
            
            if data.get('documents'):
                print(f"Found {len(data['documents'])} Strobe-related documents:")
                for i, doc in enumerate(data['documents']):
                    metadata = doc.get('metadata', {})
                    score = data.get('scores', [0])[i] if i < len(data.get('scores', [])) else 0
                    
                    print(f"\n{i+1}. {metadata.get('file_name', 'Unknown')} (Score: {score:.3f})")
                    print(f"   Entity: {metadata.get('entity_name', 'Unknown')}")
                    print(f"   Type: {metadata.get('document_type', 'Unknown')}")
            else:
                print("No Strobe documents found in vector database")
                
        else:
            print(f"Error: HTTP {response.status_code}")
            
    except Exception as e:
        print(f"Error searching for Strobe: {e}")

if __name__ == "__main__":
    print("Checking Vector Database Contents...")
    search_vector_db()
    search_strobe_specifically()
