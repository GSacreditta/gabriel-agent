# Gmail Email Scanning Configuration

## 🔧 Environment Variables (.env)

**These are credentials and environment-specific settings:**

```env
# Gmail API Configuration (Required)
GMAIL_CLIENT_ID=your_gmail_client_id_here
GMAIL_CLIENT_SECRET=your_gmail_client_secret_here
GMAIL_CREDENTIALS_DIR=config/credentials
```

## ⚙️ Application Configuration

**To customize email scanning behavior, edit `app/services/email_scanning_service.py`:**

### **📧 Approved Senders**
```python
self.approved_senders = [
    "@trustedpartner.com",           # Any email from this domain
    "@clientcompany.com", 
    "documents@yourcompany.com",     # Specific email address
    "john.doe@supplier.com",         # Individual trusted senders
]
```

### **📋 Subject Line Patterns**
```python
self.subject_patterns = [
    r"document.*review",             # "Document for review", "Document review needed"
    r"urgent.*review",               # "Urgent review required"
    r"financial.*report",            # "Financial report attached"
    r"contract.*approval",           # "Contract approval needed"
    r"invoice.*processing",          # "Invoice for processing"
    r"\.pdf$|\.docx?$|\.xlsx?$",    # Subject mentions file extensions
]
```

### **⏰ Business Hours & Timing**
```python
self.scan_interval_minutes = 15     # Scan every 15 minutes
self.business_hours = {
    'start': 8,                     # 8 AM EST
    'end': 18,                      # 6 PM EST
    'timezone': 'US/Eastern'
}
```

### **🏷️ Gmail Labels**
```python
self.labels = {
    'processed': 'SM18_APP/Processed',
    'pending': 'SM18_AP/Pending',
    'duplicates': 'SM18_AP/Duplicates',
    'errors': 'SM18_AP/Errors'
}
```

## 🔧 Customization Examples

### **Add More Approved Senders**
```python
self.approved_senders = [
    "@company1.com",
    "@company2.com",
    "finance@supplier.com",
    "contracts@partner.org",
]
```

### **Custom Subject Patterns**
```python
self.subject_patterns = [
    r"expense.*report",             # Expense reports
    r"receipt.*attached",           # Receipt attachments
    r"PO.*\d+",                     # Purchase orders with numbers
    r"quote.*request",              # Quote requests
]
```

### **Different Business Hours**
```python
self.business_hours = {
    'start': 8,                     # 8 AM
    'end': 17,                      # 5 PM
    'timezone': 'US/EST'        # EST time
}
```

## 🔒 Security Best Practices

1. **Never commit credentials to git**
2. **Keep .env file private**
3. **Use specific sender patterns** (avoid too broad patterns)
4. **Review approved senders regularly**
5. **Monitor Gmail label activity**

## 🧪 Testing Configuration

```bash
# Test your configuration
python test_gmail_setup.py

# Check what emails would be processed
# (Shows email analysis without processing)
```

## 📝 Adding New Email Sources

To add a new trusted email source:

1. **Add to approved_senders list**
2. **Add subject patterns if needed**
3. **Test with preview mode**
4. **Monitor for a few days**
5. **Adjust patterns as needed**

## 🚨 Troubleshooting

**Common Issues:**
- **No emails processed**: Check approved_senders patterns
- **Wrong emails processed**: Review subject_patterns
- **Outside business hours**: Check timezone and hours
- **Missing labels**: Service will auto-create them 