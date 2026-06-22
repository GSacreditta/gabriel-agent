#!/usr/bin/env python3
"""
Simple Vector Database Test - Check if FAISS has any documents
"""

import requests
import json

def test_faiss_info():
    """Test FAISS info endpoint"""
    try:
        response = requests.get(
            "https://gabriel-agent-709613591310.us-east1.run.app/faiss/info",
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print("=== FAISS INFO ===")
            print(f"Status: {data.get('status')}")
            print(f"Message: {data.get('message')}")
            
            service_status = data.get('service_status', {})
            print(f"Vector Service Active: {service_status.get('vector_service_active')}")
            print(f"Embedding Service Active: {service_status.get('embedding_service_active')}")
            print(f"Cloud Storage Enabled: {service_status.get('cloud_storage_enabled')}")
            
            # Check document count if available
            if 'document_count' in service_status:
                print(f"Document Count: {service_status['document_count']}")
            
            return True
        else:
            print(f"FAISS info failed: HTTP {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"Error testing FAISS info: {e}")
        return False

def test_faiss_search():
    """Test FAISS search with simple query"""
    try:
        # Try GET method first
        response = requests.get(
            "https://gabriel-agent-709613591310.us-east1.run.app/faiss/search?query=test&top_k=5",
            timeout=30
        )
        
        if response.status_code == 405:  # Method not allowed
            print("GET method not allowed, trying POST...")
            
            # Try POST method
            response = requests.post(
                "https://gabriel-agent-709613591310.us-east1.run.app/faiss/search?query=test&top_k=5",
                timeout=30
            )
        
        if response.status_code == 200:
            data = response.json()
            print("\n=== FAISS SEARCH TEST ===")
            print(f"Status: {data.get('status')}")
            
            documents = data.get('documents', [])
            print(f"Documents found: {len(documents)}")
            
            if documents:
                print("Sample documents:")
                for i, doc in enumerate(documents[:3]):
                    metadata = doc.get('metadata', {})
                    content = doc.get('content', '')[:100] + "..." if len(doc.get('content', '')) > 100 else doc.get('content', '')
                    print(f"  {i+1}. {metadata.get('file_name', 'Unknown')}")
                    print(f"     Content: {content}")
            else:
                print("No documents found in vector database")
            
            return True
            
        else:
            print(f"FAISS search failed: HTTP {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"Error testing FAISS search: {e}")
        return False

def test_manual_scan():
    """Test manual scan endpoint"""
    try:
        response = requests.post(
            "https://gabriel-agent-709613591310.us-east1.run.app/manual-scan",
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            print("\n=== MANUAL SCAN TEST ===")
            print(f"Status: {data.get('status')}")
            print(f"Message: {data.get('message')}")
            
            result = data.get('result', {})
            if result:
                print(f"Scan result: {result}")
            
            return True
            
        else:
            print(f"Manual scan failed: HTTP {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"Error testing manual scan: {e}")
        return False

if __name__ == "__main__":
    print("Testing Vector Database and Document Processing...")
    print("=" * 50)
    
    # Test 1: FAISS Info
    faiss_info_ok = test_faiss_info()
    
    # Test 2: FAISS Search
    faiss_search_ok = test_faiss_search()
    
    # Test 3: Manual Scan
    manual_scan_ok = test_manual_scan()
    
    print("\n" + "=" * 50)
    print("SUMMARY:")
    print(f"FAISS Info: {'✅' if faiss_info_ok else '❌'}")
    print(f"FAISS Search: {'✅' if faiss_search_ok else '❌'}")
    print(f"Manual Scan: {'✅' if manual_scan_ok else '❌'}")
    
    if not any([faiss_info_ok, faiss_search_ok, manual_scan_ok]):
        print("\n🚨 All tests failed - system has major issues")
    elif faiss_info_ok and not faiss_search_ok:
        print("\n🔍 FAISS service works but no documents stored")
    elif all([faiss_info_ok, faiss_search_ok, manual_scan_ok]):
        print("\n✅ All systems working - investigate why agent can't access content")