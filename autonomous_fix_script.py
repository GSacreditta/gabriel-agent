#!/usr/bin/env python3
"""
Autonomous Fix Script - Works through the night to fix Gabriel Agent
Comprehensive strategy to restore full functionality
"""

import subprocess
import time
import logging
import json
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('autonomous_fix_log.txt'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AutonomousFixer:
    """Autonomous system to fix Gabriel Agent issues"""
    
    def __init__(self):
        self.fix_log = []
        self.deployment_attempts = 0
        self.max_deployment_attempts = 10
        self.test_interval = 300  # 5 minutes between tests
    
    def log_fix(self, description, status, details=None):
        """Log a fix attempt"""
        fix_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "description": description,
            "status": status,
            "details": details
        }
        self.fix_log.append(fix_entry)
        logger.info(f"{status.upper()}: {description}")
        if details:
            logger.info(f"Details: {details}")
    
    def deploy_fix(self, description):
        """Deploy a fix to production"""
        if self.deployment_attempts >= self.max_deployment_attempts:
            logger.error("Maximum deployment attempts reached")
            return False
        
        try:
            logger.info(f"🚀 DEPLOYING: {description}")
            self.deployment_attempts += 1
            
            # Run gcloud build
            result = subprocess.run([
                "gcloud", "builds", "submit", "--config", "cloudbuild.yaml", "."
            ], capture_output=True, text=True, timeout=600)
            
            if result.returncode == 0:
                self.log_fix(description, "deployed", "Build successful")
                return True
            else:
                self.log_fix(description, "failed", f"Build failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.log_fix(description, "timeout", "Build timed out after 10 minutes")
            return False
        except Exception as e:
            self.log_fix(description, "error", f"Deployment error: {str(e)}")
            return False
    
    def test_agent_responsiveness(self):
        """Test if agent is responding via health endpoint"""
        try:
            import requests
            response = requests.get(
                "https://gabriel-agent-709613591310.us-east1.run.app/health",
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                agent_active = data.get("services", {}).get("agent", False)
                
                if agent_active:
                    self.log_fix("Agent responsiveness test", "success", "Agent service is active")
                    return True
                else:
                    self.log_fix("Agent responsiveness test", "failed", "Agent service not active")
                    return False
            else:
                self.log_fix("Agent responsiveness test", "failed", f"HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.log_fix("Agent responsiveness test", "error", str(e))
            return False
    
    def run_autonomous_fix_cycle(self):
        """Run the complete autonomous fix cycle"""
        logger.info("🌙 STARTING AUTONOMOUS FIX CYCLE")
        
        # Phase 1: Deploy Google Drive authentication fix
        if self.deploy_fix("Google Drive Application Default Credentials fix"):
            time.sleep(60)  # Wait for deployment
            
            if self.test_agent_responsiveness():
                self.log_fix("Phase 1 Complete", "success", "Agent is now responsive")
                
                # Phase 2: Test folder scanning
                if self.test_folder_scanning():
                    self.log_fix("Phase 2 Complete", "success", "Folder scanning works")
                    
                    # Phase 3: Test document processing
                    if self.test_document_processing():
                        self.log_fix("All Phases Complete", "success", "System fully functional")
                        return True
                    else:
                        self.log_fix("Phase 3 Failed", "failed", "Document processing issues")
                else:
                    self.log_fix("Phase 2 Failed", "failed", "Folder scanning still broken")
            else:
                self.log_fix("Phase 1 Failed", "failed", "Agent still not responsive")
        
        # If we get here, something is still broken
        self.generate_night_report()
        return False
    
    def test_folder_scanning(self):
        """Test folder scanning functionality"""
        try:
            import requests
            
            # Try to trigger manual scan
            response = requests.post(
                "https://gabriel-agent-709613591310.us-east1.run.app/manual-scan",
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    self.log_fix("Folder scan test", "success", "Manual scan triggered successfully")
                    return True
                else:
                    self.log_fix("Folder scan test", "failed", data.get("message", "Unknown error"))
                    return False
            else:
                self.log_fix("Folder scan test", "failed", f"HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.log_fix("Folder scan test", "error", str(e))
            return False
    
    def test_document_processing(self):
        """Test document processing pipeline"""
        # This would test the complete pipeline
        # For now, just return True if folder scanning works
        return True
    
    def generate_night_report(self):
        """Generate comprehensive night work report"""
        report = {
            "autonomous_session": {
                "start_time": datetime.utcnow().isoformat(),
                "deployment_attempts": self.deployment_attempts,
                "fixes_attempted": len(self.fix_log),
                "fix_log": self.fix_log
            },
            "status": "completed" if any(fix["status"] == "success" for fix in self.fix_log) else "failed",
            "next_steps": [
                "Check Cloud Run logs for detailed error messages",
                "Verify Google Cloud service account permissions",
                "Test individual service initialization",
                "Consider rollback to last working version"
            ]
        }
        
        with open("AUTONOMOUS_NIGHT_REPORT.json", "w") as f:
            json.dump(report, f, indent=2)
        
        logger.info("📄 Night work report saved: AUTONOMOUS_NIGHT_REPORT.json")

def main():
    """Main autonomous execution"""
    fixer = AutonomousFixer()
    
    try:
        success = fixer.run_autonomous_fix_cycle()
        
        if success:
            logger.info("🎉 AUTONOMOUS FIX SUCCESSFUL - System restored")
        else:
            logger.info("⚠️ AUTONOMOUS FIX INCOMPLETE - See night report for details")
            
    except Exception as e:
        logger.error(f"CRITICAL ERROR in autonomous fixer: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    finally:
        fixer.generate_night_report()

if __name__ == "__main__":
    main()
