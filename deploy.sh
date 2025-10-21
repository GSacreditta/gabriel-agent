#!/bin/bash
set -e  # Exit on any error

# ============================================================================
# Gabriel Agent Deployment Script
# ============================================================================
# This script deploys the Gabriel Agent to Google Cloud Run with proper
# Cloud SQL configuration.
#
# Features:
# - Builds container image
# - Deploys to Cloud Run with Cloud SQL connection
# - Validates deployment
# - Tests database connectivity
#
# Usage: ./deploy.sh [--skip-build] [--dev]
# ============================================================================

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="location-19291"
SERVICE_NAME="gabriel-agent"
REGION="us-east1"
CLOUD_SQL_INSTANCE="location-19291:us-east1:gabriel-agent-db"
SERVICE_ACCOUNT="sm18-pa@${PROJECT_ID}.iam.gserviceaccount.com"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Parse command line arguments
SKIP_BUILD=false
DEV_MODE=false

for arg in "$@"; do
  case $arg in
    --skip-build)
      SKIP_BUILD=true
      shift
      ;;
    --dev)
      DEV_MODE=true
      shift
      ;;
    --help)
      echo "Usage: ./deploy.sh [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --skip-build    Skip the container build step"
      echo "  --dev           Deploy in development mode (no min instances)"
      echo "  --help          Show this help message"
      exit 0
      ;;
  esac
done

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}🚀 Gabriel Agent Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "Project:     ${GREEN}${PROJECT_ID}${NC}"
echo -e "Service:     ${GREEN}${SERVICE_NAME}${NC}"
echo -e "Region:      ${GREEN}${REGION}${NC}"
echo -e "Cloud SQL:   ${GREEN}${CLOUD_SQL_INSTANCE}${NC}"
echo ""

# Verify we're in the right directory
if [ ! -f "Dockerfile" ]; then
  echo -e "${RED}❌ Error: Dockerfile not found${NC}"
  echo "Please run this script from the project root directory"
  exit 1
fi

# Verify gcloud is configured
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null)
if [ "$CURRENT_PROJECT" != "$PROJECT_ID" ]; then
  echo -e "${YELLOW}⚠️  Setting project to ${PROJECT_ID}${NC}"
  gcloud config set project ${PROJECT_ID}
fi

# Check authentication
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
  echo -e "${RED}❌ Error: Not authenticated with gcloud${NC}"
  echo "Please run: gcloud auth login"
  exit 1
fi

# Build container image
if [ "$SKIP_BUILD" = false ]; then
  echo -e "${BLUE}📦 Building container image...${NC}"
  gcloud builds submit \
    --tag ${IMAGE_NAME} \
    --project ${PROJECT_ID} \
    --timeout=20m
  
  echo -e "${GREEN}✅ Container build complete${NC}"
  echo ""
else
  echo -e "${YELLOW}⏩ Skipping build step${NC}"
  echo ""
fi

# Prepare deployment command
DEPLOY_CMD="gcloud run deploy ${SERVICE_NAME} \
  --image ${IMAGE_NAME} \
  --region ${REGION} \
  --platform managed \
  --allow-unauthenticated \
  --add-cloudsql-instances ${CLOUD_SQL_INSTANCE} \
  --set-env-vars USE_SECRET_MANAGER=true \
  --service-account ${SERVICE_ACCOUNT} \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 10 \
  --project ${PROJECT_ID}"

# Add min instances for production, skip for dev
if [ "$DEV_MODE" = false ]; then
  DEPLOY_CMD="${DEPLOY_CMD} --min-instances 0"
fi

# Deploy to Cloud Run
echo -e "${BLUE}🚢 Deploying to Cloud Run...${NC}"
echo -e "${YELLOW}Configuration:${NC}"
echo "  - Cloud SQL instance: ${CLOUD_SQL_INSTANCE}"
echo "  - Memory: 2Gi"
echo "  - CPU: 2"
echo "  - Max instances: 10"
echo "  - Min instances: 0"
echo "  - Service account: ${SERVICE_ACCOUNT}"
echo ""

eval ${DEPLOY_CMD}

echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""

# Get service URL
echo -e "${BLUE}🌐 Retrieving service URL...${NC}"
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
  --region ${REGION} \
  --format 'value(status.url)' \
  --project ${PROJECT_ID})

echo -e "${GREEN}Service URL: ${SERVICE_URL}${NC}"
echo ""

# Validate deployment
echo -e "${BLUE}🔍 Validating deployment...${NC}"

# Test 1: Health endpoint
echo -e "${YELLOW}Test 1: Health endpoint${NC}"
if curl -s -f ${SERVICE_URL}/health > /dev/null; then
  HEALTH_RESPONSE=$(curl -s ${SERVICE_URL}/health)
  echo -e "${GREEN}✅ Health endpoint responding${NC}"
  echo "Response: ${HEALTH_RESPONSE}" | head -c 200
  echo ""
else
  echo -e "${RED}❌ Health endpoint not responding${NC}"
fi
echo ""

# Test 2: Verify Cloud SQL configuration
echo -e "${YELLOW}Test 2: Cloud SQL configuration${NC}"
CLOUDSQL_INSTANCES=$(gcloud run services describe ${SERVICE_NAME} \
  --region ${REGION} \
  --format="value(spec.template.metadata.annotations['run.googleapis.com/cloudsql-instances'])" \
  --project ${PROJECT_ID})

if [ "$CLOUDSQL_INSTANCES" = "$CLOUD_SQL_INSTANCE" ]; then
  echo -e "${GREEN}✅ Cloud SQL instance configured: ${CLOUDSQL_INSTANCES}${NC}"
else
  echo -e "${RED}❌ Cloud SQL instance NOT configured${NC}"
  echo "Expected: ${CLOUD_SQL_INSTANCE}"
  echo "Got: ${CLOUDSQL_INSTANCES}"
fi
echo ""

# Test 3: Check recent logs for database connection
echo -e "${YELLOW}Test 3: Database connection logs${NC}"
echo "Checking for database initialization messages..."

sleep 5  # Wait for service to initialize

gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=${SERVICE_NAME} AND \
  (textPayload=~'Database' OR textPayload=~'database')" \
  --limit 10 \
  --format="table(timestamp,textPayload)" \
  --project ${PROJECT_ID} \
  --freshness=5m

echo ""

# Test 4: Test database query via API
echo -e "${YELLOW}Test 4: Database query via API${NC}"
DB_TEST_RESPONSE=$(curl -s -X POST ${SERVICE_URL}/agents/message \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "DB_AGENT",
    "action": "list_entities",
    "data": {}
  }')

if echo "$DB_TEST_RESPONSE" | grep -q "Database service not initialized"; then
  echo -e "${RED}❌ Database connection FAILED${NC}"
  echo "Response: ${DB_TEST_RESPONSE}"
  echo ""
  echo -e "${YELLOW}Troubleshooting steps:${NC}"
  echo "1. Check Cloud SQL instance is running:"
  echo "   gcloud sql instances describe gabriel-agent-db"
  echo ""
  echo "2. Verify service account has cloudsql.client role:"
  echo "   gcloud projects get-iam-policy ${PROJECT_ID} \\"
  echo "     --flatten='bindings[].members' \\"
  echo "     --filter='bindings.members:${SERVICE_ACCOUNT}'"
  echo ""
  echo "3. Check detailed logs:"
  echo "   gcloud logging read \"resource.type=cloud_run_revision AND \\"
  echo "     resource.labels.service_name=${SERVICE_NAME}\" \\"
  echo "     --limit 50"
else
  echo -e "${GREEN}✅ Database query successful${NC}"
  echo "Response preview: ${DB_TEST_RESPONSE}" | head -c 200
  echo ""
fi
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}📊 Deployment Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Service URL:     ${GREEN}${SERVICE_URL}${NC}"
echo -e "Health endpoint: ${GREEN}${SERVICE_URL}/health${NC}"
echo -e "API docs:        ${GREEN}${SERVICE_URL}/docs${NC}"
echo ""
echo -e "${YELLOW}Quick commands:${NC}"
echo ""
echo "# View logs:"
echo "gcloud logging tail \"resource.type=cloud_run_revision AND resource.labels.service_name=${SERVICE_NAME}\""
echo ""
echo "# Test database:"
echo "curl -X POST ${SERVICE_URL}/agents/message -H 'Content-Type: application/json' -d '{\"agent_type\":\"DB_AGENT\",\"action\":\"list_entities\",\"data\":{}}'"
echo ""
echo "# Update service (without rebuilding):"
echo "./deploy.sh --skip-build"
echo ""
echo -e "${GREEN}🎉 Deployment script complete!${NC}"
