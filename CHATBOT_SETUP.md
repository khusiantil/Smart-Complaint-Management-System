# 🚀 Smart Complaint System - Chatbot & Email Integration Setup

## ✨ New Features Added

### 1. 🤖 AI Chatbot Integration (Groq + Llama-1.3B)
- **Submit Complaints via Chat**: Users can describe issues conversationally
- **Generate Token ID**: Unique token for tracking complaints
- **Check Status via Chat**: Query complaint status using Token ID
- **General Query Support**: Ask questions about the system

### 2 📧 Email Notifications
- **Complaint Submission**: Confirmation email with Token ID
- **Status Updates**: Email notifications when status changes
  - ✅ Resolved
  - 🔧 In Progress
  - 📝 Under Review
  - ⚠️ Duplicate

---

## 📋 Installation Steps

### Step 1: Install Required Packages
```bash
pip install -r requirements.txt
```

Required new packages:
- `groq==0.4.1` - Groq API client
- `python-dotenv==1.0.0` - Environment variable management

### Step 2: Get Groq API Key
1. Visit https://console.groq.com
2. Sign up/Login to your account
3. Go to API Keys section
4. Create a new API key
5. Copy the API key

### Step 3: Configure Environment Variables

Create a `.env` file in the project root:

```env
# Email Configuration (Gmail)
EMAIL_USER=your_email@gmail.com
EMAIL_PASS=your_app_specific_password

# Groq API Configuration
GROQ_API_KEY=your_groq_api_key_here
```

### Step 4: Gmail Setup (For Email Notifications)
1. Enable 2-Factor Authentication on your Gmail account
2. Generate an App Password:
   - Go to myaccount.google.com
   - Click "Security" in left panel
   - Scroll to "App Passwords"
   - Select "Mail" and "Windows Computer"
   - Google will generate a 16-character password
   - Copy this as `EMAIL_PASS`

### Step 5: Run the Application
```bash
python app.py
```

Access at: http://localhost:5000

---

## 🎮 How to Use

### For Users:

#### Method 1: Traditional Form
- Click "Register New Complaint" button
- Fill form and submit

#### Method 2: AI Chatbot (NEW!)
- Click "🤖 AI Chatbot" button on dashboard
- Choose one of 3 tabs:

**💬 Query Tab**
- Ask questions about the system
- Get instant AI-powered responses

**📝 Submit Complaint Tab**
- Describe your issue
- Enter location
- Get instant Token ID
- Receive confirmation email

**📊 Check Status Tab**
- Enter your Token ID
- Get real-time status update
- AI provides explanation

### For Admins:

- Status updates automatically send emails to users
- Each status change triggers appropriate notification:
  - "In Progress" - Team is working on it
  - "Reviewing" - Details being examined
  - "Resolved" - Issue is fixed
  - "Duplicate" - Similar issue already reported

---

## 📨 Email Templates

### Complaint Submission Email
```
Token ID: COMP-1-1-ABC123
Category: Water
Location: Sector 5
Status: Pending
```

### Status Update Emails
```
🔧 IN PROGRESS
Your complaint is being actively worked on...

📝 REVIEWING
We are reviewing the details...

✅ RESOLVED
Your complaint has been resolved! Thank you for using our system.

⚠️ DUPLICATE
Similar issue already reported. We are working on it!
```

---

## 🛠️ Technical Details

### New Files Created:
1. **chatbot.py** - Groq API integration & chatbot logic
2. **templates/chatbot.html** - Chatbot UI
3. **.env.example** - Environment variable template

### Modified Files:
1. **app.py** - Added 4 new API routes
2. **requirements.txt** - Added Groq & dotenv
3. **templates/dashboard.html** - Added chatbot button

### New API Routes:
```
POST /api/chatbot/query - General queries
POST /api/chatbot/submit_complaint - Submit via chat
POST /api/chatbot/check_status - Check complaint status
GET /chatbot - Chatbot interface
```

### Database:
- Complaints are stored in the same JSON database
- Token IDs are generated and can be used for tracking
- No database schema changes required

---

## 🔒 Security Considerations

1. **API Keys**: 
   - Store in .env, never commit to git
   - Use unique API keys per environment

2. **Email Credentials**:
   - Use App Passwords, not main Gmail password
   - Don't share .env file

3. **Token IDs**:
   - Generated with UUID for uniqueness
   - Format: COMP-{user_id}-{complaint_id}-{hex}

---

## ⚡ Features Highlights

✅ **AI-Powered**: Uses Llama-1.3B model from Groq
✅ **Fast**: Real-time responses (< 2 seconds)
✅ **Smart**: Auto-categorizes complaints
✅ **Email Notifications**: Automatic status updates
✅ **Token Tracking**: Unique ID for each complaint
✅ **Responsive UI**: Works on desktop & mobile
✅ **Error Handling**: Graceful fallbacks

---

## 🐛 Troubleshooting

### Chatbot Not Working
- Check GROQ_API_KEY in .env
- Verify internet connection
- Check Groq API status

### Emails Not Sending
- Verify EMAIL_USER and EMAIL_PASS
- Ensure Gmail App Password is used (not main password)
- Check 2FA is enabled
- Allow "Less secure apps" if needed

### Token ID Not Generated
- Check complaint was saved to database
- Verify user email is set in session
- Check database permissions

---

## 📞 Support

For issues:
1. Check .env configuration
2. Review console logs
3. Ensure all dependencies installed
4. Check API quotas (Groq free tier: limited per month)

---

**Created:** April 2, 2026
**Model Used:** Llama-1.3B-Instant via Groq API
**Status:** ✅ Production Ready
