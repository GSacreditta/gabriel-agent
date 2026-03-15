# Database Connection Fix - Quick Start Guide

## 🎯 Problem Identified

Your Gabriel Agent application cannot connect to the Cloud SQL database because **Cloud Run is not configured to connect to the Cloud SQL instance**. The app code is correct, but the deployment is missing a critical configuration flag.

---

## ✅ SOLUTION 1: Quick Fix (RECOMMENDED - 5 minutes)

### What We'll Do:
Run a deployment script that redeploys your service with the correct Cloud SQL configuration.

### Steps:

1. **Make the deployment script executable:**
```bash
chmod +x deploy.sh
```

2. **Run the deployment:**
```bash
./deploy.sh
```

That's it! The script will:
- Build your container
- Deploy to Cloud Run with `--add-cloudsql-instances` flag  
- Validate the deployment
- Test the database connection
- Show you the results

### Expected Outcome:
```
✅ Cloud SQL instance configured: location-19291:us-east1:gabriel-agent-db
✅ Database query successful
```

### If It Fails:
The script will show you detailed troubleshooting steps and logs. Most common issues:
- Service account missing `Cloud SQL Client` role
- Cloud SQL instance not running
- Network configuration issues

---

## ✅ SOLUTION 2: Add Connection Fallback (BACKUP PLAN)

### What We'll Do:
Update the database service code to try multiple connection methods (Unix socket first, then public IP as fallback).

### When to Use This:
- If Solution 1 doesn't work
- For better local development experience
- To debug connection issues

### Steps:

1. **Backup the current database service:**
```bash
cp app/core/database/service.py app/core/database/service_original.py
```

2. **Replace with the improved version:**
```bash
cp app/core/database/service_with_fallback.py app/core/database/service.py
```

3. **Authorize public IP access (temporarily):**
```bash
# WARNING: This opens your database to the internet
# Only do this for debugging with a strong password
gcloud sql instances patch gabriel-agent-db \
  --authorized-networks=0.0.0.0/0 \
  --project location-19291
```

4. **Redeploy:**
```bash
./deploy.sh
```

5. **After fixing, restore security:**
```bash
# Remove public access once you've fixed the Cloud SQL connection
gcloud sql instances patch gabriel-agent-db \
  --clear-authorized-networks \
  --project location-19291
```

### Expected Outcome:
The database service will log which connection method succeeded:
```
✅ Database service initialized successfully via unix_socket
```
or if fallback:
```
⚠️ Unix socket connection failed, attempting public IP fallback...
✅ Database service initialized successfully via public IP
```

---

## 📊 Which Solution Should You Use?

| Scenario | Recommended Solution |
|----------|---------------------|
| **Just want it to work NOW** | Solution 1 |
| **Production deployment** | Solution 1 |
| **Solution 1 failed** | Try Solution 2 |
| **Need local development** | Solution 2 |
| **Debugging connection issues** | Solution 2 |

---

## 🔍 What Was Wrong?

### The Technical Details:

1. **Your code is correct:** The database service properly checks for `DB_CONNECTION_NAME` and uses Unix socket connection:
   ```python
   if db_connection_name:
       connection_string = f"postgresql+asyncpg://...@/{db_name}?host=/cloudsql/{connection_name}"
   ```

2. **The problem:** Cloud Run needs explicit configuration to mount the Cloud SQL Unix socket at `/cloudsql/`:
   ```bash
   # This flag was MISSING from your deployment:
   --add-cloudsql-instances location-19291:us-east1:gabriel-agent-db
   ```

3. **What happens:** Without this flag:
   - Cloud Run doesn't mount `/cloudsql/` directory
   - Unix socket connection fails silently
   - Database service returns "not initialized"
   - All database queries fail

4. **The fix:** Add the flag during deployment, which tells Cloud Run to:
   - Mount the Cloud SQL Proxy socket at `/cloudsql/`
   - Establish secure connection to your Cloud SQL instance
   - Allow your app to connect via Unix socket

---

## 🧪 Testing Your Fix

After deployment, run these tests:

### Test 1: Check Cloud SQL Configuration
```bash
gcloud run services describe gabriel-agent \
  --region us-east1 \
  --format="value(spec.template.metadata.annotations['run.googleapis.com/cloudsql-instances'])"
```
**Expected:** `location-19291:us-east1:gabriel-agent-db`

### Test 2: Test Database Query
```bash
curl -X POST https://gabriel-agent-ymerndhsba-ue.a.run.app/agents/message \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "DB_AGENT",
    "action": "list_entities",
    "data": {}
  }'
```
**Expected:** JSON response WITHOUT "Database service not initialized"

### Test 3: Check Logs
```bash
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=gabriel-agent AND \
  textPayload=~'Database service initialized successfully'" \
  --limit 5
```
**Expected:** Log entries showing successful database initialization

---

## 📝 Quick Reference

### Your Database Configuration:
- **Instance:** gabriel-agent-db
- **Connection Name:** location-19291:us-east1:gabriel-agent-db  
- **Database:** gabriel_agent
- **User:** gabriel_app
- **Region:** us-east1

### Files Created for You:
1. **`DATABASE_ISSUE_ANALYSIS.md`** - Full technical analysis with 4 different solution approaches
2. **`deploy.sh`** - Automated deployment script with proper Cloud SQL configuration
3. **`service_with_fallback.py`** - Improved database service with connection fallback logic
4. **`DB_FIX_SUMMARY.md`** - This quick start guide

---

## 🆘 If You Need Help

### Common Issues:

**Issue:** `Cloud SQL instance not found`
```bash
# Verify instance exists and is running:
gcloud sql instances describe gabriel-agent-db
```

**Issue:** `Permission denied`
```bash
# Check service account has cloudsql.client role:
gcloud projects get-iam-policy location-19291 \
  --flatten="bindings[].members" \
  --filter="bindings.members:sm18-pa@location-19291.iam.gserviceaccount.com"
```

**Issue:** `Build timeout`
```bash
# Use skip-build flag to deploy without rebuilding:
./deploy.sh --skip-build
```

---

## ⏱️ Time Estimates

- **Solution 1:** 5-10 minutes (includes build + deploy)
- **Solution 2:** 15-20 minutes (includes code changes + testing)
- **Verification:** 2-3 minutes

---

## 🎉 Success Criteria

You'll know it's fixed when:

1. ✅ Health endpoint returns healthy status
2. ✅ Database queries work without "Database service not initialized" error
3. ✅ Logs show "Database service initialized successfully"  
4. ✅ Cloud Run service shows Cloud SQL instance in configuration
5. ✅ Your scheduled jobs can process documents

---

## 📞 Next Steps

1. **Try Solution 1 first** - Run `./deploy.sh`
2. **Verify it works** - Run the tests above
3. **If it fails** - Check the troubleshooting output from the script
4. **Still stuck?** - Try Solution 2 with connection fallback

Good luck! 🚀
