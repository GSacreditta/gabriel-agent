# 🚀 Simplified Gabriel Agent Setup (Using Existing Service Account)

Since you already have `sm18-pa@location-19291.iam.gserviceaccount.com` with **Owner** permissions, we can skip creating new service accounts!

## ✅ What You Already Have:
- **Service Account**: `sm18-pa@location-19291.iam.gserviceaccount.com` (Owner role)
- **Google Cloud CLI**: Installed and authenticated
- **Project**: `location-19291` configured
- **Deployment Files**: `Dockerfile`, `cloudbuild.yaml`, etc. ready

## 🎯 Only 2 Steps Remaining:

### Step 1: Enable Required APIs (2 minutes)

**Via Google Cloud Console:**
1. Go to: https://console.cloud.google.com/apis/library?project=location-19291
2. Search and enable these 4 APIs:
   - **Cloud Build API** 
   - **Cloud Run API**
   - **Container Registry API** 
   - **Secret Manager API**

### Step 2: Set Up Secrets (Optional but Recommended)

**Quick Secret Setup:**
1. Go to: https://console.cloud.google.com/security/secret-manager?project=location-19291
2. Create these secrets from your `.env` file:
   - `openai-api-key` → Your OpenAI API key
   - `slack-bot-token` → Your Slack bot token
   - `db-password` → Your database password

## 🚀 Deploy!

Once APIs are enabled, deploy with:

```bash
# Build and deploy to Cloud Run
gcloud builds submit --config=cloudbuild.yaml --project=location-19291
```

## 📊 Simplified Architecture:

```
Your Code → Cloud Build → Container Registry → Cloud Run
                ↓
        Uses: sm18-pa service account (existing)
        APIs: Cloud Build, Cloud Run, Container Registry
        Secrets: Secret Manager (optional)
```

## 🎉 Benefits of Using Existing Service Account:
- **Faster setup** - No IAM configuration needed
- **Already has Owner permissions** - Can do everything
- **One less thing to manage** - Reuse existing infrastructure

---

**Next Action**: Enable the 4 APIs above, then run the deploy command! 