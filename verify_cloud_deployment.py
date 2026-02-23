 already#!/usr/bin/env python3
"""
Verify Cloud Deployment Configuration
Quick script to verify the cloud-native configuration is working
"""

import os
import sys
from pathlib import Path

def check_environment():
    """Check environment configuration"""
    print("🔍 ENVIRONMENT VERIFICATION")
    print("=" * 40)

    # Check if .env file exists (should not override in cloud)
    env_exists = Path(".env").exists()
    print(f"📄 .env file present: {'❌ YES (will override cloud vars)' if env_exists else '✅ NO (cloud vars will work)'}")

    # Check critical environment variables
    critical_vars = {
        'USE_SECRET_MANAGER': 'true',
        'DEBUG': 'false',
        'FAISS_USE_CLOUD_STORAGE': 'true',
        'GOOGLE_CLOUD_PROJECT': None,  # Should exist
    }

    print("\n🔧 CRITICAL ENVIRONMENT VARIABLES:")
    all_good = True

    for var, expected in critical_vars.items():
        value = os.environ.get(var, '')
        if expected:
            status = "✅" if value.lower() == expected else "❌"
            print(f"  {status} {var}: {value} (expected: {expected})")
            if value.lower() != expected:
                all_good = False
        else:
            status = "✅" if value else "❌"
            print(f"  {status} {var}: {'[SET]' if value else '[NOT SET]'}")
            if not value:
                all_good = False

    return all_good

def check_files():
    """Check file security"""
    print("\n🔒 FILE SECURITY CHECK")
    print("=" * 40)

    security_issues = []

    if Path(".env").exists():
        security_issues.append("⚠️ .env file present (contains secrets)")

    if Path("config/credentials").exists():
        security_issues.append("⚠️ config/credentials directory present (contains keys)")

    # Check for any .key or .pem files
    key_files = list(Path(".").rglob("*.key")) + list(Path(".").rglob("*.pem"))
    if key_files:
        security_issues.append(f"⚠️ Found {len(key_files)} key/cert files: {[str(f) for f in key_files[:3]]}")

    if not security_issues:
        print("✅ No security issues found")
        return True
    else:
        for issue in security_issues:
            print(f"  {issue}")
        return False

def check_dockerfile():
    """Check Dockerfile security"""
    print("\n🐳 DOCKERFILE SECURITY CHECK")
    print("=" * 40)

    dockerfile_path = Path("Dockerfile")
    if not dockerfile_path.exists():
        print("❌ Dockerfile not found")
        return False

    with open(dockerfile_path, 'r') as f:
        content = f.read()

    # Check if .env is removed from container
    if "rm -f /app/.env" in content:
        print("✅ Dockerfile removes .env file from container")
        return True
    else:
        print("❌ Dockerfile does not remove .env file from container")
        return False

def main():
    """Main verification"""
    print("🚀 GABRIEL AGENT - CLOUD DEPLOYMENT VERIFICATION")
    print("=" * 60)

    results = []
    results.append(("Environment Config", check_environment()))
    results.append(("File Security", check_files()))
    results.append(("Dockerfile Security", check_dockerfile()))

    print("\n📊 VERIFICATION SUMMARY")
    print("=" * 60)

    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {test_name}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL CHECKS PASSED - Ready for cloud deployment!")
        print("\n🚀 Next steps:")
        print("1. Build and push Docker image: gcloud builds submit --config=cloudbuild.yaml")
        print("2. Monitor deployment: gcloud run services logs read gabriel-agent")
        print("3. Test endpoints: curl https://your-service-url/health")
    else:
        print("⚠️ SOME CHECKS FAILED - Review issues above before deployment")
        print("\n🔧 Common fixes:")
        print("- Remove or secure .env file")
        print("- Remove local credentials directory")
        print("- Ensure Dockerfile removes .env file")

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
