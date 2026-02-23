# 🚨 Google Cloud Cost Optimization Guide
## **KEEPING YOUR SERVICES, REDUCING YOUR BILL**

## **IMMEDIATE COST REDUCTION ACTIONS**

### 1. **Cloud SQL Optimization (SAVES $15-50/month)**
```bash
# In Google Cloud Console:
# 1. Go to SQL > Instances > gabriel-agent-db
# 2. Click EDIT
# 3. Under Machine Configuration:
#    - Change from n1-standard-1 to db-f1-micro (FREE tier)
#    - Or db-g1-small ($7/month instead of $25+)
# 4. Under Storage:
#    - Reduce from 10GB to 1GB (minimum)
#    - Enable automatic backups: OFF (saves $2-5/month)
# 5. Under Connections:
#    - Reduce max connections from 100 to 10
```

### 2. **Cloud Storage Optimization (SAVES $2-10/month)**
```bash
# 1. Go to Cloud Storage > Buckets
# 2. Find gabriel-agent-faiss bucket
# 3. Click on bucket > Lifecycle
# 4. Add rule:
#    - Delete objects older than 30 days (for development)
#    - Change storage class to Nearline (cheaper for infrequent access)
# 5. Check bucket size - delete unused files
```

### 3. **API Usage Optimization (SAVES $5-20/month)**
```bash
# Google Drive API:
# 1. Go to APIs & Services > Dashboard
# 2. Find Google Drive API
# 3. Set quotas:
#    - Requests per day: 1000 (from unlimited)
#    - Requests per 100 seconds: 100

# Gmail API:
# 1. Find Gmail API
# 2. Set quotas:
#    - Queries per day: 1000 (from unlimited)
#    - Queries per 100 seconds: 100
```

## **SMART COST OPTIMIZATION STRATEGIES**

### **Database Tier Optimization**
| Current | Optimized | Monthly Savings |
|---------|-----------|-----------------|
| n1-standard-1 (1 vCPU, 3.75GB) | db-f1-micro (0.5 vCPU, 0.6GB) | $25 → $0 (FREE) |
| 10GB storage | 1GB storage | $2 → $0.20 |
| 100 max connections | 10 max connections | $5 → $0.50 |
| **TOTAL SAVINGS** | **$32 → $0.70** | **$31.30/month** |

### **Storage Class Optimization**
```bash
# Move development data to cheaper storage:
# Standard → Nearline (50% cheaper)
# Nearline → Coldline (75% cheaper for old data)
# Archive → Deep Archive (90% cheaper for very old data)
```

### **API Quota Management**
```bash
# Set reasonable limits for development:
# - Drive API: 1000 requests/day
# - Gmail API: 1000 queries/day  
# - Vision API: 1000 requests/day
# - Storage API: 1000 requests/day
```

## **DEVELOPMENT VS PRODUCTION SETTINGS**

### **Development Mode (Cheap)**
```bash
# Database: db-f1-micro (FREE)
# Storage: 1GB Nearline
# API Quotas: 1000/day
# Backups: OFF
# Monitoring: Basic
# Estimated Cost: $2-5/month
```

### **Production Mode (Full Features)**
```bash
# Database: db-n1-standard-1 ($25+/month)
# Storage: 10GB Standard
# API Quotas: Unlimited
# Backups: ON
# Monitoring: Advanced
# Estimated Cost: $30-50/month
```

## **MONITORING AND ALERTS**

### **Set Budget Alerts**
```bash
# 1. Go to Billing > Budgets & Alerts
# 2. Create budget: $10/month for development
# 3. Set alerts at:
#    - 50% ($5) - Warning
#    - 80% ($8) - Critical
#    - 100% ($10) - Emergency
```

### **Cost Monitoring Dashboard**
```bash
# Daily check:
# - Cloud Console > Billing > Reports
# - Look for unusual spikes
# - Check API usage vs quotas
# - Monitor storage growth
```

## **AUTOMATED COST SAVINGS**

### **Scheduled Scaling**
```bash
# During development hours (9 AM - 6 PM):
# - Database: db-f1-micro (FREE)
# - Storage: Standard class

# During off-hours (6 PM - 9 AM):
# - Database: STOPPED (no cost)
# - Storage: Nearline class (cheaper)
```

### **Lifecycle Policies**
```bash
# Automatic cleanup:
# - Delete temp files after 7 days
# - Move old files to cheaper storage after 30 days
# - Archive files after 90 days
# - Delete archived files after 1 year
```

## **IMMEDIATE ACTIONS TO TAKE TODAY**

1. **✅ Change Cloud SQL to db-f1-micro (FREE tier)**
2. **✅ Reduce storage from 10GB to 1GB**
3. **✅ Disable automatic backups**
4. **✅ Set API quotas to 1000/day**
5. **✅ Enable storage lifecycle policies**
6. **✅ Set budget alert at $10/month**

## **EXPECTED MONTHLY SAVINGS**

| Service | Current Cost | Optimized Cost | Savings |
|---------|-------------|----------------|---------|
| Cloud SQL | $25-50 | $0-5 | $20-45 |
| Cloud Storage | $2-10 | $0.50-2 | $1.50-8 |
| API Calls | $5-20 | $1-5 | $4-15 |
| **TOTAL** | **$32-80** | **$1.50-12** | **$25.50-68** |

## **WHEN TO SCALE UP**

### **Development Phase (Current)**
- Use FREE tier where possible
- Minimal storage and API quotas
- Basic monitoring
- **Target: $5/month or less**

### **Testing Phase**
- Small production-like setup
- Moderate quotas and storage
- Basic monitoring and backups
- **Target: $15/month**

### **Production Phase**
- Full production setup
- Unlimited quotas
- Advanced monitoring and backups
- **Target: $30-50/month**

---

**Remember: You can always scale up when you're ready for production. For now, optimize what you have!**



