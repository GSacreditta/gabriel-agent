#!/bin/bash
# Deploy private Ollama instance to Cloud Run (GPU-enabled)
# Data never leaves your GCP project. No public LLM API involved.
#
# Prerequisites:
#   - gcloud CLI authenticated
#   - Cloud Run GPU quota enabled in us-central1
#   - Project: location-19291
#
# Usage: bash infra/ollama-cloudrun/deploy.sh

set -euo pipefail

PROJECT="location-19291"
REGION="us-central1"
SERVICE_NAME="ollama-inventory"

echo "🚀 Deploying private Ollama to Cloud Run..."
echo "   Project: $PROJECT"
echo "   Region:  $REGION"
echo "   Service: $SERVICE_NAME"
echo ""

# Build and deploy
gcloud run deploy "$SERVICE_NAME" \
  --source="$(dirname "$0")" \
  --project="$PROJECT" \
  --region="$REGION" \
  --gpu=1 \
  --gpu-type=nvidia-l4 \
  --memory=16Gi \
  --cpu=4 \
  --max-instances=1 \
  --min-instances=0 \
  --timeout=300 \
  --no-allow-unauthenticated \
  --port=11434

echo ""
echo "✅ Deployed! Get the URL:"
OLLAMA_URL=$(gcloud run services describe "$SERVICE_NAME" --project="$PROJECT" --region="$REGION" --format='value(status.url)')
echo "   OLLAMA_URL=$OLLAMA_URL"
echo ""
echo "Run the inventory with:"
echo "   python run_inventory.py --bucket=YOUR_BUCKET --ollama-url=$OLLAMA_URL"
echo ""
echo "⚠️  Service is private (--no-allow-unauthenticated)."
echo "   The inventory script uses ADC (Application Default Credentials) to call it."
echo ""
echo "To tear down after use (stop GPU billing):"
echo "   gcloud run services delete $SERVICE_NAME --project=$PROJECT --region=$REGION"
