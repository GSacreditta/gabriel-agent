#!/usr/bin/env python3
"""
Gabriel Agent Production Health Check for Google Cloud

This script verifies all services are running correctly in the Google Cloud 
production environment, including:
- Google Cloud SQL connectivity
- Google Drive API access
- Slack integration
- OpenAI API
- FAISS vector storage
- All agent services

Usage:
    python production_health_check.py [--endpoint URL] [--timeout 30]
"""

import asyncio
import sys
import os
import argparse
import json
import time
from datetime import datetime
from typing import Dict, Any
import aiohttp
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class ProductionHealthChecker:
    """Production health checker for Gabriel Agent in Google Cloud."""
    
    def __init__(self, endpoint: str = None, timeout: int = 30):
        self.endpoint = endpoint or os.getenv('GABRIEL_ENDPOINT', 'http://localhost:8080')
        self.timeout = timeout
        self.results = {}
        self.start_time = time.time()

    async def check_api_health(self) -> Dict[str, Any]:
        """Check API endpoint health."""
        print("🔍 Checking API Health...")
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            try:
                # Test root endpoint
                async with session.get(f"{self.endpoint}/") as response:
                    root_data = await response.json()
                    self.results["api_root"] = {
                        "status": "PASS" if response.status == 200 else "FAIL",
                        "response_code": response.status,
                        "data": root_data
                    }
                    print(f"✅ Root endpoint: {response.status}")
                
                # Test health endpoint
                async with session.get(f"{self.endpoint}/health") as response:
                    health_data = await response.json()
                    self.results["api_health"] = {
                        "status": "PASS" if response.status == 200 else "FAIL",
                        "response_code": response.status,
                        "data": health_data
                    }
                    
                    # Analyze service status
                    services = health_data.get("services", {})
                    active_services = [name for name, active in services.items() if active]
                    failed_services = [name for name, active in services.items() if not active]
                    
                    print(f"✅ Health endpoint: {response.status}")
                    print(f"   Active services: {len(active_services)}")
                    print(f"   Failed services: {len(failed_services)}")
                    
                    if failed_services:
                        print(f"   ⚠️  Failed: {', '.join(failed_services)}")
                
            except Exception as e:
                self.results["api_connection"] = {
                    "status": "FAIL",
                    "error": str(e)
                }
                print(f"❌ API connection failed: {e}")

    async def check_agents_status(self) -> Dict[str, Any]:
        """Check agent coordinator status."""
        print("🤖 Checking Agent Status...")
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            try:
                async with session.get(f"{self.endpoint}/agents/status") as response:
                    if response.status == 200:
                        agent_data = await response.json()
                        self.results["agents_status"] = {
                            "status": "PASS",
                            "data": agent_data
                        }
                        
                        # Analyze agent status
                        agents = agent_data.get("result", {})
                        active_agents = [name for name, status in agents.items() 
                                       if isinstance(status, dict) and status.get("status") == "active"]
                        
                        print(f"✅ Agent Status: {len(active_agents)} active agents")
                        for agent in active_agents:
                            print(f"   🤖 {agent}")
                    else:
                        self.results["agents_status"] = {
                            "status": "FAIL",
                            "response_code": response.status
                        }
                        print(f"❌ Agent status failed: {response.status}")
                        
            except Exception as e:
                self.results["agents_status"] = {
                    "status": "FAIL", 
                    "error": str(e)
                }
                print(f"❌ Agent status check failed: {e}")

    async def check_agents_capabilities(self) -> Dict[str, Any]:
        """Check agent capabilities."""
        print("🎯 Checking Agent Capabilities...")
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            try:
                async with session.get(f"{self.endpoint}/agents/capabilities") as response:
                    if response.status == 200:
                        cap_data = await response.json()
                        self.results["agents_capabilities"] = {
                            "status": "PASS",
                            "data": cap_data
                        }
                        
                        capabilities = cap_data.get("result", {})
                        total_caps = sum(len(caps) for caps in capabilities.values() if isinstance(caps, list))
                        
                        print(f"✅ Agent Capabilities: {total_caps} total capabilities")
                        for agent, caps in capabilities.items():
                            if isinstance(caps, list):
                                print(f"   🎯 {agent}: {len(caps)} capabilities")
                    else:
                        self.results["agents_capabilities"] = {
                            "status": "FAIL",
                            "response_code": response.status
                        }
                        print(f"❌ Agent capabilities failed: {response.status}")
                        
            except Exception as e:
                self.results["agents_capabilities"] = {
                    "status": "FAIL",
                    "error": str(e)
                }
                print(f"❌ Agent capabilities check failed: {e}")

    async def check_faiss_vector_storage(self) -> Dict[str, Any]:
        """Check FAISS vector storage."""
        print("🔍 Checking FAISS Vector Storage...")
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            try:
                # Test FAISS info endpoint
                async with session.get(f"{self.endpoint}/faiss/info") as response:
                    if response.status == 200:
                        faiss_data = await response.json()
                        self.results["faiss_info"] = {
                            "status": "PASS",
                            "data": faiss_data
                        }
                        print(f"✅ FAISS Info: Available")
                        
                        # Test search functionality
                        search_payload = {
                            "query": "test search",
                            "top_k": 3
                        }
                        
                        async with session.post(f"{self.endpoint}/faiss/search", 
                                              json=search_payload) as search_response:
                            if search_response.status == 200:
                                search_data = await search_response.json()
                                self.results["faiss_search"] = {
                                    "status": "PASS",
                                    "data": search_data
                                }
                                print(f"✅ FAISS Search: Working")
                            else:
                                self.results["faiss_search"] = {
                                    "status": "FAIL",
                                    "response_code": search_response.status
                                }
                                print(f"⚠️ FAISS Search: {search_response.status}")
                    else:
                        self.results["faiss_info"] = {
                            "status": "FAIL",
                            "response_code": response.status
                        }
                        print(f"❌ FAISS Info failed: {response.status}")
                        
            except Exception as e:
                self.results["faiss_vector"] = {
                    "status": "FAIL",
                    "error": str(e)
                }
                print(f"❌ FAISS vector storage check failed: {e}")

    async def test_document_processing(self) -> Dict[str, Any]:
        """Test document processing functionality."""
        print("📄 Testing Document Processing...")
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
            try:
                # Test document extraction
                test_payload = {
                    "file_name": "production_test.txt",
                    "content": "This is a production test document for Gabriel Agent system verification.",
                    "entity_name": "Production Test Entity"
                }
                
                async with session.post(f"{self.endpoint}/extraction/extract-document", 
                                      params=test_payload) as response:
                    if response.status == 200:
                        extract_data = await response.json()
                        self.results["document_processing"] = {
                            "status": "PASS",
                            "data": extract_data
                        }
                        print(f"✅ Document Processing: Working")
                        
                        # Check extraction quality
                        if extract_data.get("result"):
                            print(f"   📊 Extraction successful")
                    else:
                        self.results["document_processing"] = {
                            "status": "FAIL",
                            "response_code": response.status
                        }
                        print(f"❌ Document processing failed: {response.status}")
                        
            except Exception as e:
                self.results["document_processing"] = {
                    "status": "FAIL",
                    "error": str(e)
                }
                print(f"❌ Document processing test failed: {e}")

    def generate_production_report(self) -> Dict[str, Any]:
        """Generate production health report."""
        execution_time = time.time() - self.start_time
        
        # Calculate overall health
        total_checks = len(self.results)
        passed_checks = sum(1 for result in self.results.values() 
                          if result.get("status") == "PASS")
        
        success_rate = (passed_checks / total_checks * 100) if total_checks > 0 else 0
        
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "endpoint": self.endpoint,
            "execution_time_seconds": round(execution_time, 2),
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "success_rate": success_rate,
            "overall_status": "HEALTHY" if success_rate >= 80 else "DEGRADED" if success_rate >= 60 else "CRITICAL",
            "checks": self.results
        }
        
        return report

    async def run_production_check(self) -> Dict[str, Any]:
        """Run complete production health check."""
        print("🚀 Gabriel Agent Production Health Check")
        print(f"🎯 Target: {self.endpoint}")
        print("=" * 60)
        
        try:
            # Run all checks
            await self.check_api_health()
            await self.check_agents_status()
            await self.check_agents_capabilities()
            await self.check_faiss_vector_storage()
            await self.test_document_processing()
            
        except Exception as e:
            print(f"💥 Unexpected error: {e}")
            self.results["unexpected_error"] = {
                "status": "FAIL",
                "error": str(e)
            }
        
        # Generate report
        report = self.generate_production_report()
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 PRODUCTION HEALTH SUMMARY")
        print("=" * 60)
        print(f"🎯 Overall Status: {report['overall_status']}")
        print(f"📈 Success Rate: {report['success_rate']:.1f}%")
        print(f"✅ Passed: {report['passed_checks']}/{report['total_checks']}")
        print(f"⏱️  Execution Time: {report['execution_time_seconds']}s")
        
        if report['overall_status'] == "HEALTHY":
            print("🎉 Production system is HEALTHY and ready!")
        elif report['overall_status'] == "DEGRADED":
            print("⚠️  Production system has some issues but is functional")
        else:
            print("🚨 Production system has critical issues!")
        
        return report

async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Gabriel Agent Production Health Check")
    parser.add_argument("--endpoint", help="API endpoint to check (default: localhost:8080)")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds")
    parser.add_argument("--output", help="Output file for JSON report")
    
    args = parser.parse_args()
    
    checker = ProductionHealthChecker(
        endpoint=args.endpoint,
        timeout=args.timeout
    )
    
    report = await checker.run_production_check()
    
    # Save report if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\n💾 Report saved to: {args.output}")
    
    # Exit with appropriate code
    sys.exit(0 if report['overall_status'] == "HEALTHY" else 1)

if __name__ == "__main__":
    asyncio.run(main())
