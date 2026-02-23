# Gabriel Agent Cloud Deployment Guide

## Prerequisites

1. **Google Cloud CLI** installed and authenticated
   ```bash
   gcloud auth login
   gcloud config set project location-19291
   ```

2. **Required APIs enabled**:
   - Cloud Run API
   - Cloud Build API
   - Secret Manager API
   - Cloud SQL API
   - Cloud Storage API

## Quick Deployment

### Option 1: Automated Deployment
```bash
python deploy_to_cloud.py
```

### Option 2: Manual Deployment

#### Step 1: Set up secrets in Google Cloud Secret Manager
```bash
# Create secrets
gcloud secrets create OPENAI_API_KEY --project=location-19291
gcloud secrets create SLACK_BOT_TOKEN --project=location-19291
gcloud secrets create SLACK_APP_TOKEN --project=location-19291
gcloud secrets create SLACK_SIGNING_SECRET --project=location-19291
gcloud secrets create DB_PASSWORD --project=location-19291
gcloud secrets create google-service-account-key --project=location-19291

# Add secret values
echo 'your-openai-api-key' | gcloud secrets versions add OPENAI_API_KEY --data-file=- --project=location-19291
echo 'your-slack-bot-token' | gcloud secrets versions add SLACK_BOT_TOKEN --data-file=- --project=location-19291
echo 'your-slack-app-token' | gcloud secrets versions add SLACK_APP_TOKEN --data-file=- --project=location-19291
echo 'your-slack-signing-secret' | gcloud secrets versions add SLACK_SIGNING_SECRET --data-file=- --project=location-19291
echo 'Gabriel@19291' | gcloud secrets versions add DB_PASSWORD --data-file=- --project=location-19291
```

#### Step 2: Deploy to Cloud Run
```bash
gcloud builds submit --config cloudbuild.yaml --project=location-19291
```

## Configuration

The application is configured with:
- **Port**: 8081
- **Memory**: 2GB
- **CPU**: 2 cores
- **Region**: us-east1
- **Database**: Cloud SQL (location-19291:us-east1:gabriel-agent-db)
- **Storage**: Cloud Storage for FAISS vectors

## Environment Variables

The following environment variables are set automatically:
- `USE_SECRET_MANAGER=true`
- `GOOGLE_CLOUD_PROJECT=location-19291`
- `DB_CONNECTION_NAME=location-19291:us-east1:gabriel-agent-db`
- `FAISS_USE_CLOUD_STORAGE=true`
- `FAISS_BUCKET_NAME=gabriel-agent-faiss`
- `DEBUG=false`

## Post-Deployment

1. **Test the deployment**:
   ```bash
   curl https://gabriel-agent-location-19291.a.run.app/health
   ```

2. **Check logs**:
   ```bash
   gcloud run services logs gabriel-agent --region=us-east1 --project=location-19291
   ```

3. **Update Slack webhook URL** to point to your deployed service

## Troubleshooting

### Common Issues

1. **Secret Manager permissions**: Ensure the service account has Secret Manager access
2. **Cloud SQL connection**: Verify the Cloud SQL instance is running and accessible
3. **Memory issues**: The app is configured for 2GB, increase if needed

### Useful Commands

```bash
# Check service status
gcloud run services describe gabriel-agent --region=us-east1 --project=location-19291

# View recent logs
gcloud run services logs gabriel-agent --region=us-east1 --project=location-19291 --limit=50

# Update service
gcloud run services update gabriel-agent --region=us-east1 --project=location-19291

# Delete service
gcloud run services delete gabriel-agent --region=us-east1 --project=location-19291
```

## Service Account Permissions

The service account `sm18-pa@location-19291.iam.gserviceaccount.com` needs:
- Cloud SQL Client
- Secret Manager Secret Accessor
- Storage Object Admin
- Cloud Run Invoker
