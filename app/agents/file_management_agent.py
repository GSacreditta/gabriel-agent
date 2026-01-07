"""
File Management Agent - File Operations Agent
Handles ALL file operations and maintains file inventory with entity validation
Connected to REAL Google Drive service
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import os
import tempfile
from .base_agent import BaseAgent


class FileManagementAgent(BaseAgent):
    """File Management Agent for all Google Drive file operations"""
    
    def __init__(self):
        super().__init__("FILE_MANAGEMENT_AGENT")
        
        # File inventory state
        self.file_inventory = {}
        self.folder_inventory = {}
        self.entity_folders = {}  # Track entity folders
        self.last_scan = None
        
        # Google Drive service integration (will be injected)
        self.drive_service = None
        
    def set_drive_service(self, drive_service):
        """Inject Google Drive service dependency"""
        self.drive_service = drive_service
        self.log_activity("Google Drive service connected", {
            "service_account": getattr(drive_service.credentials, 'service_account_email', 'unknown')
        })
    
    def connect_agent(self, agent_type: str, agent_instance):
        """Connect to another agent"""
        self.log_activity(f"Connected to {agent_type}", {"agent_type": agent_type})
    
    async def health_check(self) -> bool:
        """Check if the agent is healthy"""
        try:
            # Basic health check - agent is healthy if it has required services
            return self.drive_service is not None
        except Exception as e:
            self.log_activity("Health check failed", {"error": str(e)})
            return False
        
    async def get_capabilities(self) -> List[str]:
        """Return File Management Agent capabilities"""
        return [
            "file_scan",
            "file_move",
            "file_copy", 
            "file_delete",
            "folder_create",
            "folder_organize",
            "file_inventory_management",
            "entity_folder_validation",
            "drive_operations",
            "metadata_extraction"
        ]
    
    async def handle_message(self, source_agent: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle messages from other agents"""
        action = message.get('action')
        data = message.get('data', {})
        
        try:
            if action == "create_entity_folder":
                result = await self.create_entity_folder(data.get('entity_name'))
                return {"status": "success", "result": result}
                
            elif action == "scan_files":
                result = await self.scan_files()
                return {"status": "success", "result": result}
                
            elif action == "move_file":
                result = await self.move_file(data.get('file_id'), data.get('destination_folder_id'))
                return {"status": "success", "result": result}
                
            elif action == "get_file_metadata":
                result = await self.get_file_metadata(data.get('file_id'))
                return {"status": "success", "result": result}
                
            elif action == "download_file":
                result = await self.download_file(data.get('file_id'))
                return {"status": "success", "result": result}
                
            elif action == "organize_files_by_entity":
                result = await self.organize_files_by_entity()
                return {"status": "success", "result": result}
                
            elif action == "get_inventory":
                result = await self.get_inventory_report()
                return {"status": "success", "result": result}
                
            else:
                return {"status": "error", "message": f"Unknown action: {action}"}
                
        except Exception as e:
            self.logger.error(f"Error handling message: {e}")
            return {"status": "error", "message": str(e)}
    
    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a file management task"""
        task_type = task.get('type')
        
        if task_type == "scheduled_scan":
            return await self.scan_files()
        elif task_type == "organize_files":
            return await self.organize_files_by_entity()
        else:
            return {"status": "error", "message": f"Unknown task type: {task_type}"}
    
    async def create_entity_folder(self, entity_name: str) -> Dict[str, Any]:
        """
        Create folder for entity after validating with DB Agent
        This is the KEY FLOW mentioned in requirements
        """
        try:
            if not self.drive_service:
                return {"status": "error", "message": "Google Drive service not connected"}
                
            self.log_activity("Creating entity folder", {"entity_name": entity_name})
            
            # Step 1: Validate entity exists in database (KEY REQUIREMENT)
            db_response = await self.send_message("DB_AGENT", {
                "action": "match_entity",
                "data": {"name": entity_name}
            })
            
            if db_response.get('status') != 'success':
                return {"status": "error", "message": "Failed to validate entity with database"}
            
            entity_data = db_response.get('result')
            if not entity_data:
                # Entity doesn't exist - request HDL Agent to create it
                hdl_response = await self.send_message("HDL_AGENT", {
                    "action": "request_review",
                    "data": {
                        "type": "entity_creation",
                        "entity_name": entity_name,
                        "message": f"Entity '{entity_name}' not found. Create new entity folder?"
                    }
                })
                
                return {
                    "status": "pending_approval", 
                    "message": f"Entity folder creation pending approval for: {entity_name}",
                    "hdl_response": hdl_response
                }
            
            # Step 2: Check if folder already exists
            entity_id = entity_data['entity_id']
            folder_name = f"{entity_id}_{entity_name}"
            
            if entity_id in self.entity_folders:
                return {
                    "status": "exists",
                    "message": f"Folder already exists for entity: {entity_name}",
                    "folder_data": self.entity_folders[entity_id]
                }
            
            # Step 3: Create folder in Google Drive
            try:
                folder_result = await self.drive_service.create_folder(folder_name)
                folder_id = folder_result['id']
                
                # Store in inventory
                self.entity_folders[entity_id] = {
                    "folder_id": folder_id,
                    "folder_name": folder_name,
                    "entity_name": entity_name,
                    "entity_id": entity_id,
                    "created_at": datetime.utcnow().isoformat(),
                    "file_count": 0
                }
                
                self.log_activity("Entity folder created in Google Drive", {
                    "entity_name": entity_name,
                    "folder_id": folder_id,
                    "folder_name": folder_name,
                    "entity_id": entity_id
                })
                
                return {
                    "status": "success",
                    "folder_id": folder_id,
                    "folder_name": folder_name,
                    "entity_data": entity_data,
                    "message": f"Successfully created folder for {entity_name}"
                }
                
            except Exception as e:
                return {"status": "error", "message": f"Failed to create folder in Google Drive: {str(e)}"}
                
        except Exception as e:
            self.logger.error(f"Error creating entity folder: {e}")
            return {"status": "error", "message": str(e)}
    
    async def scan_files(self) -> Dict[str, Any]:
        """Scan Google Drive files and update inventory"""
        try:
            if not self.drive_service:
                return {"status": "error", "message": "Google Drive service not connected"}
                
            self.log_activity("File scan started")
            
            # Get all files from Google Drive
            files = await self.drive_service.get_folder_contents()
            
            # Process each file
            file_count = 0
            folder_count = 0
            new_files = 0
            
            for file in files:
                file_id = file['id']
                
                # Check if this is a new file
                if file_id not in self.file_inventory:
                    new_files += 1
                
                # Update inventory
                self.file_inventory[file_id] = {
                    "id": file_id,
                    "name": file['name'],
                    "mime_type": file.get('mimeType', 'unknown'),
                    "created_time": file.get('createdTime'),
                    "modified_time": file.get('modifiedTime'),
                    "size": file.get('size', 0),
                    "web_view_link": file.get('webViewLink'),
                    "last_scanned": datetime.utcnow().isoformat()
                }
                
                if file.get('mimeType') == 'application/vnd.google-apps.folder':
                    folder_count += 1
                    # Update folder inventory
                    self.folder_inventory[file_id] = self.file_inventory[file_id]
                else:
                    file_count += 1
            
            self.last_scan = datetime.utcnow()
            
            scan_results = {
                'scan_completed_at': self.last_scan.isoformat(),
                'total_files': file_count,
                'total_folders': folder_count,
                'new_files': new_files,
                'inventory_size': len(self.file_inventory)
            }
            
            self.log_activity("File scan completed", scan_results)
            
            return scan_results
            
        except Exception as e:
            self.logger.error(f"Error scanning files: {e}")
            return {"status": "error", "message": str(e)}
    
    async def move_file(self, file_id: str, destination_folder_id: str) -> Dict[str, Any]:
        """Move file to destination folder in Google Drive"""
        try:
            if not self.drive_service:
                return {"status": "error", "message": "Google Drive service not connected"}
                
            self.log_activity("Moving file", {
                "file_id": file_id, 
                "destination_folder_id": destination_folder_id
            })
            
            # Use Google Drive service to move file
            move_result = await self.drive_service.move_file_to_folder(file_id, destination_folder_id)
            
            # Update inventory if file exists
            if file_id in self.file_inventory:
                self.file_inventory[file_id]['last_moved'] = datetime.utcnow().isoformat()
                self.file_inventory[file_id]['current_folder'] = destination_folder_id
            
            return {
                "status": "success", 
                "message": f"File {file_id} moved successfully",
                "move_result": move_result
            }
                
        except Exception as e:
            self.logger.error(f"Error moving file: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_file_metadata(self, file_id: str) -> Dict[str, Any]:
        """Get detailed file metadata from Google Drive"""
        try:
            if not self.drive_service:
                return {"status": "error", "message": "Google Drive service not connected"}
            
            # Get metadata from Google Drive
            metadata = await self.drive_service.get_file_metadata(file_id)
            
            # Update inventory with latest metadata
            if file_id in self.file_inventory:
                self.file_inventory[file_id].update(metadata)
                self.file_inventory[file_id]['metadata_updated'] = datetime.utcnow().isoformat()
            
            return metadata
            
        except Exception as e:
            self.logger.error(f"Error getting file metadata: {e}")
            return {"status": "error", "message": str(e)}
    
    async def download_file(self, file_id: str) -> Dict[str, Any]:
        """Download file from Google Drive to temporary location"""
        try:
            if not self.drive_service:
                return {"status": "error", "message": "Google Drive service not connected"}
            
            # Download to temp file
            temp_path = await self.drive_service.download_file_to_temp(file_id)
            
            if temp_path:
                # Get file info
                file_info = self.file_inventory.get(file_id, {})
                
                return {
                    "status": "success",
                    "temp_path": temp_path,
                    "file_name": file_info.get('name', 'unknown'),
                    "file_size": os.path.getsize(temp_path) if os.path.exists(temp_path) else 0
                }
            else:
                return {"status": "error", "message": "Failed to download file"}
                
        except Exception as e:
            self.logger.error(f"Error downloading file: {e}")
            return {"status": "error", "message": str(e)}
    
    async def organize_files_by_entity(self) -> Dict[str, Any]:
        """Organize files into entity folders based on content analysis"""
        try:
            if not self.drive_service:
                return {"status": "error", "message": "Google Drive service not connected"}
            
            self.log_activity("Starting file organization by entity")
            
            # Get files that need organization (not in entity folders)
            unorganized_files = []
            for file_id, file_data in self.file_inventory.items():
                if file_data.get('mime_type') != 'application/vnd.google-apps.folder':
                    # Check if file is already in an entity folder
                    if not any(folder_id in file_data.get('current_folder', '') 
                             for folder_id in self.entity_folders.keys()):
                        unorganized_files.append(file_data)
            
            organization_results = {
                "files_processed": len(unorganized_files),
                "successfully_organized": 0,
                "needs_manual_review": 0,
                "errors": 0
            }
            
            # For each unorganized file, try to determine entity
            for file_data in unorganized_files:
                try:
                    # Send to Extraction Agent for content analysis
                    extraction_response = await self.send_message("EXTRACTION_AGENT", {
                        "action": "extract_entity_from_file",
                        "data": {"file_id": file_data['id'], "file_name": file_data['name']}
                    })
                    
                    if extraction_response.get('status') == 'success':
                        extracted_entity = extraction_response.get('result', {}).get('entity_name')
                        
                        if extracted_entity and extracted_entity in [ef['entity_name'] for ef in self.entity_folders.values()]:
                            # Find entity folder
                            entity_folder = next(
                                (ef for ef in self.entity_folders.values() if ef['entity_name'] == extracted_entity),
                                None
                            )
                            
                            if entity_folder:
                                # Move file to entity folder
                                move_result = await self.move_file(file_data['id'], entity_folder['folder_id'])
                                if move_result.get('status') == 'success':
                                    organization_results["successfully_organized"] += 1
                                else:
                                    organization_results["errors"] += 1
                            else:
                                organization_results["needs_manual_review"] += 1
                        else:
                            organization_results["needs_manual_review"] += 1
                    else:
                        organization_results["needs_manual_review"] += 1
                        
                except Exception as e:
                    self.logger.error(f"Error organizing file {file_data['name']}: {e}")
                    organization_results["errors"] += 1
            
            self.log_activity("File organization completed", organization_results)
            
            return organization_results
            
        except Exception as e:
            self.logger.error(f"Error organizing files by entity: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_inventory_report(self) -> Dict[str, Any]:
        """Generate comprehensive inventory report"""
        try:
            report = {
                "last_scan": self.last_scan.isoformat() if self.last_scan else None,
                "total_files": len([f for f in self.file_inventory.values() 
                                 if f.get('mime_type') != 'application/vnd.google-apps.folder']),
                "total_folders": len(self.folder_inventory),
                "entity_folders": len(self.entity_folders),
                "entity_folder_details": list(self.entity_folders.values()),
                "drive_service_connected": self.drive_service is not None,
                "inventory_last_updated": datetime.utcnow().isoformat()
            }
            
            # Calculate storage statistics
            total_size = sum(int(f.get('size', 0)) for f in self.file_inventory.values() 
                           if f.get('size') and f.get('size').isdigit())
            report["total_storage_bytes"] = total_size
            report["total_storage_mb"] = round(total_size / (1024 * 1024), 2)
            
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating inventory report: {e}")
            return {"status": "error", "message": str(e)} 