#!/usr/bin/env python3
"""
Cloud Native Validation Test
Validates that the Gabriel Agent system is properly configured for Google Cloud deployment
"""

import os
import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime
import requests

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

class CloudNativeValidator:
    """Validates cloud-native configuration and functionality"""

    def __init__(self):
        self.results = {
            "timestamp": datetime.utcnow().isoformat(),
            "environment": "unknown",
            "tests": {},
            "overall_status": "unknown"
        }

    def detect_environment(self):
        """Detect if running locally or in cloud"""
        # Check for cloud environment indicators
        cloud_indicators = [
            "KUBERNETES_SERVICE_HOST",  # Kubernetes
            "GAE_ENV",  # Google App Engine
            "GOOGLE_CLOUD_PROJECT",  # Cloud Run
            "CLOUD_RUN_JOB",  # Cloud Run Job
        ]

        is_cloud = any(os.environ.get(indicator) for indicator in cloud_indicators)

        # Check for local development indicators
        local_indicators = [
            Path(".env").exists(),
            Path("config/credentials").exists(),
            os.getcwd().startswith("C:\\Users")  # Windows local path
        ]

        is_local = any(local_indicators)

        if is_cloud:
            self.results["environment"] = "cloud"
        elif is_local:
            self.results["environment"] = "local"
        else:
            self.results["environment"] = "unknown"

        return self.results["environment"]

    def test_secret_manager_configuration(self):
        """Test Secret Manager configuration"""
        test_name = "secret_manager_config"

        try:
            # Check if USE_SECRET_MANAGER is set to true
            use_secret_manager = os.environ.get('USE_SECRET_MANAGER', '').lower() == 'true'

            # Check if .env file exists (should not in cloud)
            env_file_exists = Path(".env").exists()

            # Check if secrets are loaded from environment (not from .env)
            secrets_in_env = any(
                os.environ.get(secret) for secret in [
                    'OPENAI_API_KEY', 'SLACK_BOT_TOKEN', 'DB_PASSWORD'
                ]
            )

            self.results["tests"][test_name] = {
                "status": "pass" if use_secret_manager and not env_file_exists and secrets_in_env else "fail",
                "use_secret_manager": use_secret_manager,
                "env_file_exists": env_file_exists,
                "secrets_in_env": secrets_in_env,
                "details": {
                    "USE_SECRET_MANAGER": os.environ.get('USE_SECRET_MANAGER'),
                    "env_file_present": env_file_exists,
                    "secrets_loaded": secrets_in_env
                }
            }

        except Exception as e:
            self.results["tests"][test_name] = {
                "status": "error",
                "error": str(e)
            }

    def test_cloud_storage_configuration(self):
        """Test Cloud Storage configuration"""
        test_name = "cloud_storage_config"

        try:
            # Check FAISS cloud storage settings
            faiss_cloud = os.environ.get('FAISS_USE_CLOUD_STORAGE', '').lower() == 'true'
            bucket_name = os.environ.get('FAISS_BUCKET_NAME', '')
            persist_dir = os.environ.get('FAISS_PERSIST_DIRECTORY', '')

            # Check if bucket exists (would need actual cloud access to verify)
            bucket_configured = bool(bucket_name)

            self.results["tests"][test_name] = {
                "status": "pass" if faiss_cloud and bucket_configured else "fail",
                "faiss_use_cloud_storage": faiss_cloud,
                "bucket_name": bucket_name,
                "persist_directory": persist_dir,
                "details": {
                    "FAISS_USE_CLOUD_STORAGE": os.environ.get('FAISS_USE_CLOUD_STORAGE'),
                    "FAISS_BUCKET_NAME": bucket_name,
                    "FAISS_PERSIST_DIRECTORY": persist_dir
                }
            }

        except Exception as e:
            self.results["tests"][test_name] = {
                "status": "error",
                "error": str(e)
            }

    def test_google_cloud_authentication(self):
        """Test Google Cloud authentication"""
        test_name = "google_auth_config"

        try:
            # Check for service account authentication
            creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '')
            project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', '')

            # In cloud, should use service account (no explicit credentials file)
            is_service_account = not creds_path and project_id

            # Check if local credentials file exists (should not in cloud)
            local_creds_exist = Path("config/credentials").exists() if creds_path else False

            self.results["tests"][test_name] = {
                "status": "pass" if is_service_account and not local_creds_exist else "fail",
                "service_account_auth": is_service_account,
                "credentials_path": creds_path,
                "project_id": project_id,
                "local_creds_exist": local_creds_exist,
                "details": {
                    "GOOGLE_APPLICATION_CREDENTIALS": creds_path,
                    "GOOGLE_CLOUD_PROJECT": project_id,
                    "local_credentials_detected": local_creds_exist
                }
            }

        except Exception as e:
            self.results["tests"][test_name] = {
                "status": "error",
                "error": str(e)
            }

    def test_environment_variables(self):
        """Test critical environment variables"""
        test_name = "environment_variables"

        try:
            critical_vars = {
                'DEBUG': 'false',
                'USE_SECRET_MANAGER': 'true',
                'FAISS_USE_CLOUD_STORAGE': 'true',
                'GOOGLE_CLOUD_PROJECT': None,  # Should exist
                'DB_HOST': None,  # Should exist
            }

            var_status = {}
            all_correct = True

            for var_name, expected_value in critical_vars.items():
                actual_value = os.environ.get(var_name, '')
                if expected_value:
                    is_correct = actual_value.lower() == expected_value
                else:
                    is_correct = bool(actual_value)  # Should exist

                var_status[var_name] = {
                    "value": actual_value,
                    "expected": expected_value,
                    "correct": is_correct
                }

                if not is_correct:
                    all_correct = False

            self.results["tests"][test_name] = {
                "status": "pass" if all_correct else "fail",
                "variables": var_status,
                "all_correct": all_correct
            }

        except Exception as e:
            self.results["tests"][test_name] = {
                "status": "error",
                "error": str(e)
            }

    def test_security_configuration(self):
        """Test security-related configurations"""
        test_name = "security_config"

        try:
            # Check for local development files that shouldn't be in cloud
            security_issues = []

            if Path(".env").exists():
                security_issues.append(".env file present (should not be in cloud)")

            if Path("config/credentials").exists():
                security_issues.append("config/credentials directory present (should not be in cloud)")

            # Check for hardcoded local paths in environment
            if os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '').startswith('C:\\'):
                security_issues.append("Hardcoded Windows path in GOOGLE_APPLICATION_CREDENTIALS")

            # Check DEBUG mode
            if os.environ.get('DEBUG', '').lower() == 'true':
                security_issues.append("DEBUG mode enabled (should be false in production)")

            self.results["tests"][test_name] = {
                "status": "pass" if not security_issues else "fail",
                "security_issues": security_issues,
                "issues_count": len(security_issues)
            }

        except Exception as e:
            self.results["tests"][test_name] = {
                "status": "error",
                "error": str(e)
            }

    def test_service_architecture(self):
        """Test service architecture configuration"""
        test_name = "service_architecture"

        try:
            # Import and test service initialization
            from app.core.config import get_settings

            settings = get_settings()

            # Test that settings load correctly
            settings_loaded = settings is not None

            # Test critical service configurations
            services_config = {
                "vector_service": {
                    "use_cloud_storage": getattr(settings, 'FAISS_USE_CLOUD_STORAGE', False),
                    "bucket_name": getattr(settings, 'FAISS_BUCKET_NAME', ''),
                },
                "secret_manager": {
                    "enabled": os.environ.get('USE_SECRET_MANAGER', '').lower() == 'true'
                }
            }

            self.results["tests"][test_name] = {
                "status": "pass" if settings_loaded else "fail",
                "settings_loaded": settings_loaded,
                "services_config": services_config
            }

        except Exception as e:
            self.results["tests"][test_name] = {
                "status": "error",
                "error": str(e),
                "traceback": str(e.__traceback__)
            }

    def run_all_tests(self):
        """Run all validation tests"""
        print("🚀 Starting Cloud Native Validation Tests")
        print("=" * 60)

        # Detect environment
        env = self.detect_environment()
        print(f"📍 Environment detected: {env}")
        print()

        # Run all tests
        test_methods = [
            self.test_secret_manager_configuration,
            self.test_cloud_storage_configuration,
            self.test_google_cloud_authentication,
            self.test_environment_variables,
            self.test_security_configuration,
            self.test_service_architecture
        ]

        for test_method in test_methods:
            print(f"🧪 Running {test_method.__name__}...")
            test_method()

        # Calculate overall status
        passed_tests = sum(1 for test in self.results["tests"].values()
                          if test.get("status") == "pass")
        total_tests = len(self.results["tests"])

        self.results["overall_status"] = "pass" if passed_tests == total_tests else "fail"

        return self.results

    def generate_report(self):
        """Generate validation report"""
        print("\n📊 CLOUD NATIVE VALIDATION REPORT")
        print("=" * 60)
        print(f"Environment: {self.results['environment']}")
        print(f"Timestamp: {self.results['timestamp']}")
        print(f"Overall Status: {'✅ PASS' if self.results['overall_status'] == 'pass' else '❌ FAIL'}")
        print()

        for test_name, test_result in self.results["tests"].items():
            status_icon = "✅" if test_result["status"] == "pass" else "❌" if test_result["status"] == "fail" else "⚠️"
            print(f"{status_icon} {test_name}: {test_result['status']}")

            if test_result["status"] == "fail":
                if "security_issues" in test_result:
                    for issue in test_result["security_issues"]:
                        print(f"   🔴 {issue}")
                if "variables" in test_result:
                    for var_name, var_info in test_result["variables"].items():
                        if not var_info["correct"]:
                            print(f"   🔴 {var_name}: {var_info['value']} (expected: {var_info['expected']})")

        print("\n" + "=" * 60)

        if self.results["overall_status"] == "pass":
            print("🎉 ALL TESTS PASSED - System is properly configured for Google Cloud!")
        else:
            print("⚠️  SOME TESTS FAILED - Review issues above before deployment")

        return self.results

def main():
    """Main validation execution"""
    validator = CloudNativeValidator()

    # Run all tests
    results = validator.run_all_tests()

    # Generate report
    report = validator.generate_report()

    # Save detailed results
    with open("cloud_native_validation_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    print("\n💾 Detailed results saved to: cloud_native_validation_results.json")
    return results

if __name__ == "__main__":
    results = main()
    exit(0 if results["overall_status"] == "pass" else 1)
