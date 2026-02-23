#!/usr/bin/env python3
"""
Gabriel Agent System Health Check
=================================

Comprehensive system testing script that verifies all services are running correctly.
This script tests:

1. Environment Configuration
2. Core Services (Agent, Drive, Slack, Vector Storage)
3. Database Connectivity
4. API Endpoints
5. Integration Workflows
6. Agent Architecture

Usage:
    python system_health_check.py [--quick] [--verbose] [--skip-api]
"""

import asyncio
import sys
import os
import logging
import time
import traceback
from datetime import datetime
from typing import Dict, List, Any, Optional
import argparse
import json

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"system_health_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
logger = logging.getLogger(__name__)

class SystemHealthChecker:
    """Comprehensive system health checker for Gabriel Agent."""
    
    def __init__(self, quick_mode=False, verbose=False, skip_api=False):
        self.quick_mode = quick_mode
        self.verbose = verbose
        self.skip_api = skip_api
        self.results = {
            "environment": {},
            "services": {},
            "database": {},
            "api_endpoints": {},
            "integration": {},
            "agents": {},
            "summary": {}
        }
        self.services = {}
        self.start_time = time.time()

    def log_test(self, category: str, test_name: str, status: str, details: str = "", error: str = ""):
        """Log test results in a structured format."""
        timestamp = datetime.now().isoformat()
        
        if category not in self.results:
            self.results[category] = {}
            
        self.results[category][test_name] = {
            "status": status,
            "details": details,
            "error": error,
            "timestamp": timestamp
        }
        
        # Console output
        status_emoji = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        logger.info(f"{status_emoji} [{category.upper()}] {test_name}: {status}")
        
        if details and self.verbose:
            logger.info(f"    Details: {details}")
        if error:
            logger.error(f"    Error: {error}")

    async def check_environment(self):
        """Check environment variables and configuration."""
        logger.info("🔧 Checking Environment Configuration...")
        
        required_vars = [
            "OPENAI_API_KEY",
            "GOOGLE_APPLICATION_CREDENTIALS", 
            "GOOGLE_DRIVE_FOLDER_ID",
            "SLACK_BOT_TOKEN",
            "DATABASE_URL"
        ]
        
        optional_vars = [
            "SLACK_SIGNING_SECRET",
            "SLACK_APP_TOKEN", 
            "GMAIL_CLIENT_ID",
            "GMAIL_CLIENT_SECRET"
        ]
        
        # Check required environment variables
        missing_required = []
        for var in required_vars:
            if os.getenv(var):
                self.log_test("environment", f"env_var_{var}", "PASS", f"Variable is set")
            else:
                missing_required.append(var)
                self.log_test("environment", f"env_var_{var}", "FAIL", "", f"Required variable not set")
        
        # Check optional environment variables
        for var in optional_vars:
            if os.getenv(var):
                self.log_test("environment", f"env_var_{var}", "PASS", f"Optional variable is set")
            else:
                self.log_test("environment", f"env_var_{var}", "WARN", f"Optional variable not set")
        
        # Check configuration files
        try:
            from app.core.config import get_settings
            settings = get_settings()
            self.log_test("environment", "config_loading", "PASS", "Configuration loaded successfully")
        except Exception as e:
            self.log_test("environment", "config_loading", "FAIL", "", str(e))
        
        # Check Google credentials file
        creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if creds_path and os.path.exists(creds_path):
            self.log_test("environment", "google_credentials_file", "PASS", f"File exists: {creds_path}")
        else:
            self.log_test("environment", "google_credentials_file", "FAIL", "", "Credentials file not found")
        
        return len(missing_required) == 0

    async def check_database_connectivity(self):
        """Test database connectivity."""
        logger.info("🗄️ Checking Database Connectivity...")
        
        try:
            from sqlalchemy.ext.asyncio import create_async_engine
            from sqlalchemy import text
            
            database_url = os.getenv('DATABASE_URL')
            if not database_url:
                self.log_test("database", "connection", "FAIL", "", "DATABASE_URL not set")
                return False
            
            # Test basic connection
            engine = create_async_engine(database_url, echo=False)
            
            async with engine.begin() as conn:
                # Test connection
                result = await conn.execute(text("SELECT version();"))
                version = result.fetchone()[0]
                self.log_test("database", "connection", "PASS", f"PostgreSQL: {version[:50]}...")
                
                # Test current database
                result = await conn.execute(text("SELECT current_database();"))
                db_name = result.fetchone()[0]
                self.log_test("database", "database_name", "PASS", f"Connected to: {db_name}")
                
                # Test user permissions
                result = await conn.execute(text("SELECT current_user;"))
                user = result.fetchone()[0]
                self.log_test("database", "user_permissions", "PASS", f"Connected as: {user}")
                
            await engine.dispose()
            return True
            
        except ImportError as e:
            self.log_test("database", "dependencies", "FAIL", "", f"Missing database dependencies: {e}")
            return False
        except Exception as e:
            self.log_test("database", "connection", "FAIL", "", str(e))
            return False

    async def check_core_services(self):
        """Test core services initialization."""
        logger.info("⚙️ Checking Core Services...")
        
        # Test Agent service
        try:
            from app.services.agent import create_agent
            agent = create_agent()
            self.services["agent"] = agent
            self.log_test("services", "agent_service", "PASS", "Agent service created successfully")
        except Exception as e:
            self.log_test("services", "agent_service", "FAIL", "", str(e))
        
        # Test Google Drive service
        try:
            from app.services.google_drive import GoogleDriveService
            drive_service = GoogleDriveService()
            self.services["drive_service"] = drive_service
            
            # Test basic functionality if not in quick mode
            if not self.quick_mode:
                files = await drive_service.get_folder_contents()
                self.log_test("services", "google_drive_service", "PASS", f"Drive service working, found {len(files) if files else 0} files")
            else:
                self.log_test("services", "google_drive_service", "PASS", "Drive service initialized")
        except Exception as e:
            self.log_test("services", "google_drive_service", "FAIL", "", str(e))
        
        # Test Vector Storage service
        try:
            from app.services.vector_storage_service import VectorStorageService
            vector_service = VectorStorageService(use_temp_dir=True)
            self.services["vector_service"] = vector_service
            
            # Test basic functionality
            stats = vector_service.get_collection_stats()
            self.log_test("services", "vector_storage_service", "PASS", f"Vector storage initialized")
        except Exception as e:
            self.log_test("services", "vector_storage_service", "FAIL", "", str(e))
        
        # Test OCR service
        try:
            from app.services.ocr_service import OCRService
            ocr_service = OCRService()
            self.services["ocr_service"] = ocr_service
            self.log_test("services", "ocr_service", "PASS", "OCR service initialized")
        except Exception as e:
            self.log_test("services", "ocr_service", "FAIL", "", str(e))
        
        # Test PDF service
        try:
            from app.services.pdf_service import PDFService
            pdf_service = PDFService()
            self.services["pdf_service"] = pdf_service
            self.log_test("services", "pdf_service", "PASS", "PDF service initialized")
        except Exception as e:
            self.log_test("services", "pdf_service", "FAIL", "", str(e))
        
        # Test Slack service
        try:
            from app.services.slack_service import SlackService
            slack_service = SlackService()
            
            # Initialize with agent if available
            if self.services.get("agent"):
                await slack_service.initialize(self.services["agent"])
                self.log_test("services", "slack_service", "PASS", "Slack service initialized with agent")
            else:
                self.log_test("services", "slack_service", "WARN", "Slack service created but not fully initialized")
                
            self.services["slack_service"] = slack_service
        except Exception as e:
            self.log_test("services", "slack_service", "FAIL", "", str(e))
        
        return len([k for k, v in self.services.items() if v is not None]) >= 3

    async def check_agent_architecture(self):
        """Test the agent coordinator and individual agents."""
        logger.info("🤖 Checking Agent Architecture...")
        
        try:
            from app.agents.agent_coordinator import AgentCoordinator
            
            # Initialize Agent Coordinator
            agent_coordinator = AgentCoordinator()
            start_result = await agent_coordinator.start_coordinator()
            
            if start_result.get("status") == "success":
                self.log_test("agents", "agent_coordinator", "PASS", f"Coordinator started with {len(start_result.get('agents', {}))} agents")
                self.services["agent_coordinator"] = agent_coordinator
                
                # Test agent status
                agent_status = await agent_coordinator.get_agent_status()
                active_agents = [name for name, status in agent_status.items() if status.get("status") == "active"]
                self.log_test("agents", "agent_status", "PASS", f"Active agents: {len(active_agents)}")
                
                # Test agent capabilities
                capabilities = await agent_coordinator.get_agent_capabilities()
                self.log_test("agents", "agent_capabilities", "PASS", f"Total capabilities: {len(capabilities) if capabilities else 0}")
                
                # Test basic message routing if not in quick mode
                if not self.quick_mode and "DB_AGENT" in active_agents:
                    try:
                        test_response = await agent_coordinator.route_message(
                            source="HEALTH_CHECK",
                            target="DB_AGENT",
                            message={"action": "health_check", "data": {}}
                        )
                        if test_response.get("status") == "success":
                            self.log_test("agents", "message_routing", "PASS", "Message routing working")
                        else:
                            self.log_test("agents", "message_routing", "WARN", f"Routing returned: {test_response.get('status')}")
                    except Exception as e:
                        self.log_test("agents", "message_routing", "FAIL", "", str(e))
                
            else:
                self.log_test("agents", "agent_coordinator", "FAIL", "", f"Coordinator failed to start: {start_result}")
                
        except Exception as e:
            self.log_test("agents", "agent_coordinator", "FAIL", "", str(e))

    async def check_api_endpoints(self):
        """Test FastAPI endpoints (if not skipped)."""
        if self.skip_api:
            logger.info("⏭️ Skipping API endpoint tests as requested")
            return
            
        logger.info("🌐 Checking API Endpoints...")
        
        try:
            import httpx
            
            # Test if server is running on localhost
            async with httpx.AsyncClient(timeout=10.0) as client:
                try:
                    # Test root endpoint
                    response = await client.get("http://localhost:8080/")
                    if response.status_code == 200:
                        self.log_test("api_endpoints", "root_endpoint", "PASS", f"Status: {response.status_code}")
                    else:
                        self.log_test("api_endpoints", "root_endpoint", "WARN", f"Unexpected status: {response.status_code}")
                except Exception as e:
                    self.log_test("api_endpoints", "root_endpoint", "FAIL", "", "Server not running or not accessible")
                
                try:
                    # Test health endpoint
                    response = await client.get("http://localhost:8080/health")
                    if response.status_code == 200:
                        health_data = response.json()
                        active_services = sum(1 for v in health_data.get("services", {}).values() if v)
                        self.log_test("api_endpoints", "health_endpoint", "PASS", f"Active services: {active_services}")
                    else:
                        self.log_test("api_endpoints", "health_endpoint", "WARN", f"Status: {response.status_code}")
                except Exception as e:
                    self.log_test("api_endpoints", "health_endpoint", "FAIL", "", str(e))
                
        except ImportError:
            self.log_test("api_endpoints", "dependencies", "WARN", "httpx not available for API testing")
        except Exception as e:
            self.log_test("api_endpoints", "general", "FAIL", "", str(e))

    async def check_integration_workflows(self):
        """Test basic integration workflows."""
        logger.info("🔄 Checking Integration Workflows...")
        
        # Test document processing workflow
        if self.services.get("drive_service") and self.services.get("vector_service"):
            try:
                from app.services.document_processor import DocumentProcessorService
                
                doc_processor = DocumentProcessorService()
                await doc_processor.initialize(
                    ocr_service=self.services.get("ocr_service"),
                    pdf_service=self.services.get("pdf_service"),
                    vector_service=self.services.get("vector_service"),
                    drive_service=self.services.get("drive_service"),
                    agent=self.services.get("agent"),
                    slack_service=self.services.get("slack_service")
                )
                
                self.log_test("integration", "document_processor_init", "PASS", "Document processor initialized with all services")
                
                # Test file discovery if not in quick mode
                if not self.quick_mode:
                    from app.services.file_discovery_service import FileDiscoveryService
                    
                    file_discovery = FileDiscoveryService()
                    await file_discovery.initialize(
                        self.services["drive_service"],
                        doc_processor
                    )
                    
                    scan_result = await file_discovery.scan_folder()
                    if scan_result.get("success"):
                        files_found = scan_result.get("files_processed", 0)
                        self.log_test("integration", "file_discovery_scan", "PASS", f"Found {files_found} files to process")
                    else:
                        self.log_test("integration", "file_discovery_scan", "WARN", f"Scan completed with issues: {scan_result.get('error', 'Unknown')}")
                
            except Exception as e:
                self.log_test("integration", "document_processing_workflow", "FAIL", "", str(e))
        else:
            self.log_test("integration", "document_processing_workflow", "SKIP", "Required services not available")

    async def run_existing_tests(self):
        """Run some of the existing pytest tests."""
        logger.info("🧪 Running Existing Tests...")
        
        try:
            # Test basic DB connection using existing test
            from tests.test_db_connection import test_connection
            db_result = await test_connection()
            if db_result:
                self.log_test("integration", "existing_db_test", "PASS", "Database connection test passed")
            else:
                self.log_test("integration", "existing_db_test", "FAIL", "", "Database connection test failed")
        except Exception as e:
            self.log_test("integration", "existing_db_test", "FAIL", "", str(e))
        
        # Test vector storage using existing test
        if not self.quick_mode:
            try:
                from tests.test_vector_storage import test_vector_storage
                vector_result = await test_vector_storage()
                if vector_result:
                    self.log_test("integration", "existing_vector_test", "PASS", "Vector storage test passed")
                else:
                    self.log_test("integration", "existing_vector_test", "FAIL", "", "Vector storage test failed")
            except Exception as e:
                self.log_test("integration", "existing_vector_test", "FAIL", "", str(e))

    def generate_summary(self):
        """Generate a summary of all test results."""
        logger.info("📊 Generating Test Summary...")
        
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        warnings = 0
        
        for category, tests in self.results.items():
            if category == "summary":
                continue
                
            for test_name, result in tests.items():
                total_tests += 1
                status = result.get("status", "UNKNOWN")
                if status == "PASS":
                    passed_tests += 1
                elif status == "FAIL":
                    failed_tests += 1
                elif status == "WARN":
                    warnings += 1
        
        execution_time = time.time() - self.start_time
        
        self.results["summary"] = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "warnings": warnings,
            "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
            "execution_time_seconds": round(execution_time, 2),
            "timestamp": datetime.now().isoformat(),
            "quick_mode": self.quick_mode,
            "skip_api": self.skip_api
        }
        
        # Console summary
        logger.info("=" * 60)
        logger.info("🎯 SYSTEM HEALTH CHECK SUMMARY")
        logger.info("=" * 60)
        logger.info(f"📈 Total Tests: {total_tests}")
        logger.info(f"✅ Passed: {passed_tests}")
        logger.info(f"❌ Failed: {failed_tests}")
        logger.info(f"⚠️ Warnings: {warnings}")
        logger.info(f"📊 Success Rate: {self.results['summary']['success_rate']:.1f}%")
        logger.info(f"⏱️ Execution Time: {execution_time:.2f} seconds")
        
        if failed_tests == 0:
            logger.info("🎉 ALL CRITICAL TESTS PASSED! System is healthy.")
        elif failed_tests <= 2:
            logger.info("⚠️ System mostly healthy with some minor issues.")
        else:
            logger.info("🚨 Multiple failures detected. System needs attention.")

    async def cleanup(self):
        """Clean up resources."""
        logger.info("🧹 Cleaning up resources...")
        
        for service_name, service in self.services.items():
            if service and hasattr(service, 'cleanup'):
                try:
                    if asyncio.iscoroutinefunction(service.cleanup):
                        await service.cleanup()
                    else:
                        service.cleanup()
                    logger.debug(f"Cleaned up {service_name}")
                except Exception as e:
                    logger.debug(f"Error cleaning up {service_name}: {e}")

    def save_results(self, filename: str = None):
        """Save test results to a JSON file."""
        if filename is None:
            filename = f"health_check_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump(self.results, f, indent=2, default=str)
            logger.info(f"💾 Results saved to: {filename}")
        except Exception as e:
            logger.error(f"Failed to save results: {e}")

    async def run_full_check(self):
        """Run the complete system health check."""
        logger.info("🚀 Starting Gabriel Agent System Health Check...")
        logger.info(f"Mode: {'Quick' if self.quick_mode else 'Comprehensive'}")
        logger.info(f"API Tests: {'Skipped' if self.skip_api else 'Included'}")
        logger.info("=" * 60)
        
        try:
            # Run all checks
            await self.check_environment()
            await self.check_database_connectivity()
            await self.check_core_services()
            await self.check_agent_architecture()
            await self.check_api_endpoints()
            await self.check_integration_workflows()
            await self.run_existing_tests()
            
        except KeyboardInterrupt:
            logger.warning("🛑 Health check interrupted by user")
        except Exception as e:
            logger.error(f"💥 Unexpected error during health check: {e}")
            logger.error(f"Traceback: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}")
        finally:
            # Always generate summary and cleanup
            self.generate_summary()
            await self.cleanup()
            self.save_results()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Gabriel Agent System Health Check")
    parser.add_argument("--quick", action="store_true", help="Run quick tests only")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--skip-api", action="store_true", help="Skip API endpoint tests")
    
    args = parser.parse_args()
    
    checker = SystemHealthChecker(
        quick_mode=args.quick,
        verbose=args.verbose,
        skip_api=args.skip_api
    )
    
    await checker.run_full_check()


if __name__ == "__main__":
    print("🏥 Gabriel Agent System Health Check")
    print("=" * 40)
    asyncio.run(main())
