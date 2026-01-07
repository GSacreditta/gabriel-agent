#!/usr/bin/env python3
"""
Deployment script for Gabriel Agent to Google Cloud Run
This script helps set up secrets and deploy the application
"""

import os
import subprocess
import sys
from pathlib import Path

def run_command(cmd, check=True):
    """Run a command and return the result"""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error running command: {cmd}")
        print(f"Error: {result.stderr}")
        sys.exit(1)
    return result

def check_prerequisites():
    """Check if required tools are installed"""
    print("Checking prerequisites...")
    
    # Check gcloud
    result = run_command("gcloud --version", check=False)
    if result.returncode != 0:
        print("ERROR: gcloud CLI not found. Please install it first.")
        print("   Visit: https://cloud.google.com/sdk/docs/install")
        sys.exit(1)
    
    # Check if logged in
    result = run_command("gcloud auth list --filter=status:ACTIVE --format='value(account)'", check=False)
    if result.returncode != 0 or not result.stdout.strip():
        print("ERROR: Not logged in to gcloud. Please run: gcloud auth login")
        sys.exit(1)
    
    print("Prerequisites check passed")

def get_project_id():
    """Get the current project ID"""
    result = run_command("gcloud config get-value project")
    project_id = result.stdout.strip()
    if not project_id:
        print("ERROR: No project set. Please run: gcloud config set project YOUR_PROJECT_ID")
        sys.exit(1)
    return project_id

def setup_secrets(project_id):
    """Set up secrets in Google Cloud Secret Manager"""
    print(f"Setting up secrets for project: {project_id}")
    
    # Read .env file
    env_file = Path(".env")
    if not env_file.exists():
        print("ERROR: .env file not found. Please create it first.")
        sys.exit(1)
    
    secrets_to_create = [
        "OPENAI_API_KEY",
        "SLACK_BOT_TOKEN", 
        "SLACK_APP_TOKEN",
        "SLACK_SIGNING_SECRET",
        "DB_PASSWORD",
        "google-service-account-key"
    ]
    
    for secret_name in secrets_to_create:
        print(f"  Creating secret: {secret_name}")
        # Check if secret already exists
        result = run_command(f"gcloud secrets describe {secret_name} --project={project_id}", check=False)
        if result.returncode == 0:
            print(f"    Secret {secret_name} already exists, skipping...")
            continue
        
        # Create the secret
        run_command(f"gcloud secrets create {secret_name} --project={project_id}")
        print(f"    Secret {secret_name} created")
        print(f"    Please add the secret value using:")
        print(f"       echo 'YOUR_SECRET_VALUE' | gcloud secrets versions add {secret_name} --data-file=- --project={project_id}")

def build_and_deploy(project_id):
    """Build and deploy the application"""
    print(f"Building and deploying to project: {project_id}")
    
    # Build and deploy using Cloud Build
    run_command(f"gcloud builds submit --config cloudbuild.yaml --project={project_id}")
    
    print("Deployment completed!")
    print(f"Your application should be available at:")
    print(f"   https://gabriel-agent-{project_id}.a.run.app")

def main():
    print("Gabriel Agent Cloud Deployment")
    print("=" * 40)
    
    # Check prerequisites
    check_prerequisites()
    
    # Get project ID
    project_id = get_project_id()
    print(f"Using project: {project_id}")
    
    # Ask user what they want to do
    print("\nWhat would you like to do?")
    print("1. Set up secrets only")
    print("2. Deploy application only")
    print("3. Set up secrets and deploy")
    
    choice = input("Enter your choice (1-3): ").strip()
    
    if choice in ["1", "3"]:
        setup_secrets(project_id)
    
    if choice in ["2", "3"]:
        build_and_deploy(project_id)
    
    print("\nDeployment process completed!")

if __name__ == "__main__":
    main()
