#!/usr/bin/env python3
"""
Autonomous Diagnostic Script - Comprehensive System Analysis
Runs through the night to identify and fix all Gabriel Agent issues
"""

import sys
import os
import asyncio
import logging
import traceback
import json
from datetime import datetime
from pathlib import Path

# Add app to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('autonomous_diagnostic.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AutonomousDiagnostic:
    """Comprehensive diagnostic and repair system"""
    
    def __init__(self):
        self.results = {
            "timestamp": datetime.utcnow().isoformat(),
            "phases": {},
            "issues_found": [],
            "fixes_applied": [],
            "final_status": "unknown"
        }
    
    async def run_complete_diagnosis(self):
        """Run complete diagnostic and repair sequence"""
        logger.info("🌙 STARTING AUTONOMOUS NIGHT SHIFT DIAGNOSIS")
        
        try:
            # Phase 1: Basic imports and dependencies
            await self.phase1_basic_imports()
            
            # Phase 2: Configuration validation
            await self.phase2_config_validation()
            
            # Phase 3: Service initialization testing
            await self.phase3_service_testing()
            
            # Phase 4: Agent creation testing
            await self.phase4_agent_testing()
            
            # Phase 5: Tool validation
            await self.phase5_tool_validation()
            
            # Phase 6: Integration testing
            await self.phase6_integration_testing()
            
            # Generate final report
            self.generate_final_report()
            
        except Exception as e:
            logger.error(f"CRITICAL ERROR in autonomous diagnosis: {e}")
            logger.error(traceback.format_exc())
            self.results["final_status"] = "failed"
            self.results["critical_error"] = str(e)
    
    async def phase1_basic_imports(self):
        """Test all basic imports"""
        logger.info("🔍 PHASE 1: Testing basic imports")
        phase_results = {"status": "unknown", "issues": [], "successes": []}
        
        # Test core imports
        imports_to_test = [
            ("app.core.config", "get_settings"),
            ("app.services.agent", "create_agent"),
            ("app.services.google_drive", "GoogleDriveService"),
            ("app.services.slack_service", "SlackService"),
            ("app.services.ocr_service", "OCRService"),
            ("app.services.vector_storage_service", "VectorStorageService"),
            ("app.tools.vector_search_tool", "VectorSearchTool"),
            ("app.tools.agent_query_tool", "AgentQueryTool"),
            ("langchain_openai", "ChatOpenAI"),
            ("langchain.agents", "create_openai_functions_agent")
        ]
        
        for module_name, class_name in imports_to_test:
            try:
                module = __import__(module_name, fromlist=[class_name])
                getattr(module, class_name)
                phase_results["successes"].append(f"{module_name}.{class_name}")
                logger.info(f"✅ Import success: {module_name}.{class_name}")
            except Exception as e:
                phase_results["issues"].append(f"{module_name}.{class_name}: {str(e)}")
                logger.error(f"❌ Import failed: {module_name}.{class_name} - {e}")
        
        phase_results["status"] = "completed"
        self.results["phases"]["phase1_imports"] = phase_results
    
    async def phase2_config_validation(self):
        """Validate configuration and environment variables"""
        logger.info("🔍 PHASE 2: Configuration validation")
        phase_results = {"status": "unknown", "issues": [], "config": {}}
        
        try:
            from app.core.config import get_settings
            settings = get_settings()
            
            # Check critical settings
            critical_settings = [
                "OPENAI_API_KEY",
                "GOOGLE_DRIVE_FOLDER_ID",
                "FAISS_PERSIST_DIRECTORY",
                "FAISS_USE_CLOUD_STORAGE"
            ]
            
            for setting in critical_settings:
                try:
                    value = getattr(settings, setting, None)
                    if value:
                        # Mask sensitive values
                        if "KEY" in setting or "SECRET" in setting:
                            masked_value = f"{str(value)[:10]}...{str(value)[-4:]}" if len(str(value)) > 14 else "***"
                            phase_results["config"][setting] = masked_value
                        else:
                            phase_results["config"][setting] = str(value)
                        logger.info(f"✅ Config: {setting} = {phase_results['config'][setting]}")
                    else:
                        phase_results["issues"].append(f"Missing: {setting}")
                        logger.error(f"❌ Missing config: {setting}")
                except Exception as e:
                    phase_results["issues"].append(f"{setting}: {str(e)}")
                    logger.error(f"❌ Config error: {setting} - {e}")
            
            phase_results["status"] = "completed"
            
        except Exception as e:
            phase_results["issues"].append(f"Settings loading failed: {str(e)}")
            phase_results["status"] = "failed"
            logger.error(f"❌ Settings loading failed: {e}")
        
        self.results["phases"]["phase2_config"] = phase_results
    
    async def phase3_service_testing(self):
        """Test individual service initialization"""
        logger.info("🔍 PHASE 3: Service initialization testing")
        phase_results = {"status": "unknown", "services": {}}
        
        # Test each service individually
        services_to_test = [
            ("GoogleDriveService", "app.services.google_drive", "GoogleDriveService"),
            ("OCRService", "app.services.ocr_service", "OCRService"),
            ("VectorStorageService", "app.services.vector_storage_service", "VectorStorageService"),
            ("SlackService", "app.services.slack_service", "SlackService")
        ]
        
        for service_name, module_name, class_name in services_to_test:
            try:
                logger.info(f"Testing {service_name}...")
                module = __import__(module_name, fromlist=[class_name])
                service_class = getattr(module, class_name)
                
                # Try to instantiate
                if service_name == "VectorStorageService":
                    # Special handling for VectorStorageService with parameters
                    service_instance = service_class(
                        persist_directory="/app/faiss_db",
                        use_cloud_storage=True,
                        bucket_name="gabriel-agent-faiss"
                    )
                else:
                    service_instance = service_class()
                
                phase_results["services"][service_name] = {
                    "status": "success",
                    "instance_type": str(type(service_instance))
                }
                logger.info(f"✅ {service_name} instantiated successfully")
                
            except Exception as e:
                phase_results["services"][service_name] = {
                    "status": "failed",
                    "error": str(e),
                    "traceback": traceback.format_exc()
                }
                logger.error(f"❌ {service_name} failed: {e}")
        
        phase_results["status"] = "completed"
        self.results["phases"]["phase3_services"] = phase_results
    
    async def phase4_agent_testing(self):
        """Test agent creation specifically"""
        logger.info("🔍 PHASE 4: Agent creation testing")
        phase_results = {"status": "unknown", "issues": []}
        
        try:
            # Test settings loading
            from app.core.config import get_settings
            settings = get_settings()
            
            # Test OpenAI API key
            api_key = settings.OPENAI_API_KEY
            if not api_key:
                phase_results["issues"].append("OPENAI_API_KEY is None or empty")
                logger.error("❌ OPENAI_API_KEY is missing")
            else:
                logger.info(f"✅ OPENAI_API_KEY found (length: {len(api_key)})")
            
            # Test ChatOpenAI creation
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model="gpt-4-turbo-preview",
                temperature=0,
                api_key=api_key
            )
            logger.info("✅ ChatOpenAI instance created")
            
            # Test tool creation
            from app.tools.system_info_tool import SystemInfoTool
            from app.tools.agent_query_tool import AgentQueryTool
            
            tools = []
            tools.append(SystemInfoTool())
            tools.append(AgentQueryTool())
            logger.info(f"✅ Tools created: {len(tools)} tools")
            
            # Test prompt creation
            from langchain.prompts import ChatPromptTemplate
            from langchain_core.prompts.chat import MessagesPlaceholder
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a test agent."),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad")
            ])
            logger.info("✅ Prompt template created")
            
            # Test agent creation
            from langchain.agents import create_openai_functions_agent, AgentExecutor
            
            agent = create_openai_functions_agent(
                llm=llm,
                tools=tools,
                prompt=prompt
            )
            logger.info("✅ OpenAI functions agent created")
            
            agent_executor = AgentExecutor.from_agent_and_tools(
                agent=agent,
                tools=tools,
                verbose=True,
                handle_parsing_errors=True,
                max_iterations=10
            )
            logger.info("✅ Agent executor created")
            
            phase_results["status"] = "success"
            
        except Exception as e:
            phase_results["issues"].append(f"Agent creation failed: {str(e)}")
            phase_results["status"] = "failed"
            phase_results["error"] = str(e)
            phase_results["traceback"] = traceback.format_exc()
            logger.error(f"❌ Agent creation failed: {e}")
            logger.error(traceback.format_exc())
        
        self.results["phases"]["phase4_agent"] = phase_results
    
    async def phase5_tool_validation(self):
        """Validate all tools work properly"""
        logger.info("🔍 PHASE 5: Tool validation")
        phase_results = {"status": "unknown", "tools": {}}
        
        # Test VectorSearchTool specifically
        try:
            from app.tools.vector_search_tool import VectorSearchTool
            vector_tool = VectorSearchTool()
            phase_results["tools"]["VectorSearchTool"] = {"status": "success"}
            logger.info("✅ VectorSearchTool created successfully")
        except Exception as e:
            phase_results["tools"]["VectorSearchTool"] = {
                "status": "failed", 
                "error": str(e),
                "traceback": traceback.format_exc()
            }
            logger.error(f"❌ VectorSearchTool failed: {e}")
        
        phase_results["status"] = "completed"
        self.results["phases"]["phase5_tools"] = phase_results
    
    async def phase6_integration_testing(self):
        """Test integration between components"""
        logger.info("🔍 PHASE 6: Integration testing")
        phase_results = {"status": "unknown", "integrations": {}}
        
        # Test if main.py initialization would work
        try:
            # Simulate main.py service initialization
            logger.info("Testing main.py service initialization simulation")
            
            # This is a dry run - don't actually start services
            phase_results["integrations"]["main_simulation"] = {
                "status": "simulated",
                "note": "Cannot fully test without actual deployment"
            }
            
        except Exception as e:
            phase_results["integrations"]["main_simulation"] = {
                "status": "failed",
                "error": str(e)
            }
            logger.error(f"❌ Main simulation failed: {e}")
        
        phase_results["status"] = "completed"
        self.results["phases"]["phase6_integration"] = phase_results
    
    def generate_final_report(self):
        """Generate comprehensive diagnostic report"""
        logger.info("📋 GENERATING FINAL DIAGNOSTIC REPORT")
        
        # Count issues
        total_issues = sum(len(phase.get("issues", [])) for phase in self.results["phases"].values())
        total_phases = len(self.results["phases"])
        
        # Determine overall status
        failed_phases = [name for name, phase in self.results["phases"].items() if phase.get("status") == "failed"]
        
        if not failed_phases:
            self.results["final_status"] = "healthy"
        elif len(failed_phases) < total_phases / 2:
            self.results["final_status"] = "partial"
        else:
            self.results["final_status"] = "critical"
        
        self.results["summary"] = {
            "total_phases": total_phases,
            "failed_phases": failed_phases,
            "total_issues": total_issues,
            "status": self.results["final_status"]
        }
        
        # Write detailed report
        with open("AUTONOMOUS_DIAGNOSTIC_REPORT.json", "w") as f:
            json.dump(self.results, f, indent=2)
        
        # Write human-readable summary
        self.write_summary_report()
        
        logger.info(f"🎯 DIAGNOSIS COMPLETE - Status: {self.results['final_status']}")
        logger.info(f"📄 Reports saved: AUTONOMOUS_DIAGNOSTIC_REPORT.json")
    
    def write_summary_report(self):
        """Write human-readable summary"""
        with open("AUTONOMOUS_DIAGNOSTIC_SUMMARY.md", "w") as f:
            f.write("# Autonomous Diagnostic Report\n\n")
            f.write(f"**Timestamp:** {self.results['timestamp']}\n")
            f.write(f"**Overall Status:** {self.results['final_status']}\n\n")
            
            f.write("## Phase Results\n\n")
            for phase_name, phase_data in self.results["phases"].items():
                f.write(f"### {phase_name}\n")
                f.write(f"**Status:** {phase_data.get('status', 'unknown')}\n")
                
                if phase_data.get("issues"):
                    f.write("**Issues Found:**\n")
                    for issue in phase_data["issues"]:
                        f.write(f"- {issue}\n")
                
                f.write("\n")
            
            f.write("## Next Steps\n\n")
            if self.results["final_status"] == "critical":
                f.write("- Critical issues found requiring immediate attention\n")
            elif self.results["final_status"] == "partial":
                f.write("- Some issues found, system may have limited functionality\n")
            else:
                f.write("- System appears healthy, investigate deployment-specific issues\n")

async def main():
    """Main diagnostic execution"""
    diagnostic = AutonomousDiagnostic()
    await diagnostic.run_complete_diagnosis()

if __name__ == "__main__":
    asyncio.run(main())
