#!/usr/bin/env python3
"""
Simple script to clear local FAISS vector database files.
This doesn't require API access or database connections.
"""

import os
import shutil
from pathlib import Path

def clear_local_faiss():
    """Clear local FAISS vector database files."""
    print("Clearing Local FAISS Vector Database")
    print("=" * 40)
    
    # FAISS directory paths to check
    faiss_dirs = [
        "faiss_db",
        "app/faiss_db", 
        "./faiss_db",
        "chroma_db",  # In case there are old ChromaDB files
        "test_chroma_db"
    ]
    
    total_cleared = 0
    
    for faiss_dir in faiss_dirs:
        path = Path(faiss_dir)
        if path.exists():
            print(f"\nFound directory: {path}")
            
            # Count files before deletion
            faiss_files = list(path.glob("*.faiss")) + list(path.glob("*.pkl")) + list(path.glob("*.db"))
            print(f"  Found {len(faiss_files)} vector database files")
            
            # Show files that will be deleted
            for file in faiss_files:
                print(f"    - {file.name}")
            
            # Confirm deletion
            if faiss_files:
                response = input(f"\nDelete {len(faiss_files)} files from {path}? (y/N): ")
                if response.lower() in ['y', 'yes']:
                    try:
                        # Delete individual files first
                        for file in faiss_files:
                            file.unlink()
                            print(f"    Deleted: {file.name}")
                        
                        # Try to remove directory if empty
                        try:
                            if not any(path.iterdir()):
                                path.rmdir()
                                print(f"    Removed empty directory: {path}")
                        except:
                            pass  # Directory not empty or permission issue
                        
                        total_cleared += len(faiss_files)
                        print(f"  Successfully cleared {len(faiss_files)} files")
                        
                    except Exception as e:
                        print(f"  Error clearing {path}: {e}")
                else:
                    print(f"  Skipped {path}")
            else:
                print(f"  No vector database files found in {path}")
        else:
            print(f"Directory not found: {faiss_dir}")
    
    print(f"\n" + "=" * 40)
    print(f"CLEARED {total_cleared} vector database files total")
    print("=" * 40)

if __name__ == "__main__":
    clear_local_faiss()
