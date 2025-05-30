import asyncio
from app.services.google_drive import GoogleDriveService

async def main():
    try:
        print("Initializing Google Drive service...")
        drive_service = GoogleDriveService()
        
        print("\nAttempting to list folder contents...")
        files = await drive_service.get_folder_contents()
        
        print(f"\nFound {len(files)} files in the folder:")
        for file in files:
            print(f"- {file['name']} (ID: {file['id']}, Type: {file['mimeType']})")
            
    except Exception as e:
        print(f"\nError accessing Google Drive: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main()) 