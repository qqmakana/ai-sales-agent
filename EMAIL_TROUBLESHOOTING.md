# Email Troubleshooting Guide

## 📧 Where to Check for Emails

### Email Address Being Sent To:
- **Recipient**: `makanaiii@outlook.com` (set in `planner.py` line 55)
- **Sender**: `sandtonstreets@gmail.com` (set in `cli.py` line 13)

### Check These Places:
1. **Inbox** - Check `makanaiii@outlook.com` inbox
2. **Spam/Junk Folder** - Emails might be filtered
3. **Promotions Tab** (Gmail) - If using Gmail
4. **Terminal Output** - Check for error messages

---

## 🔍 How to Debug Email Issues

### Step 1: Check Terminal Output
When you run an automation, look at the terminal where `app.py` is running. You should see:
```
[DEBUG] Email password check: password_length=16, will_simulate=False
[DEBUG] Sending email with body length: XXX
```

### Step 2: Check Automation Result
In the dashboard, click on your automation to see the full result. It should show:
- ✅ "Email sent successfully to makanaiii@outlook.com" (if successful)
- ⚠️ "Email simulated" (if no password)
- ❌ "Error sending email: [error message]" (if failed)

### Step 3: Common Issues

#### Issue 1: Email Going to Spam
**Solution**: Check spam folder in `makanaiii@outlook.com`

#### Issue 2: Gmail App Password Not Working
**Solution**: 
1. Go to Google Account → Security
2. Enable 2-Step Verification
3. Generate new App Password
4. Update password in `cli.py` line 12

#### Issue 3: Email Not Being Sent
**Check**:
- Terminal for error messages
- Automation result in dashboard
- Email credentials are correct

---

## 🧪 Test Email Sending

### Quick Test:
1. Create automation: "Email Sarah the daily summary"
2. Check terminal output
3. Check dashboard result
4. Check email inbox (and spam folder)

### Expected Result:
- Terminal: Shows email sending debug messages
- Dashboard: Shows "Email sent successfully"
- Email: Should arrive in `makanaiii@outlook.com` inbox

---

## 📝 Current Email Configuration

**File**: `cli.py` (lines 12-13)
```python
os.environ["EMAIL_PASSWORD"] = "mdrf gyhb wfci szqj"  # Gmail app password
os.environ["EMAIL_SENDER"] = "sandtonstreets@gmail.com"  # Sender email
```

**File**: `planner.py` (line 55)
```python
arguments={"to": "makanaiii@outlook.com", "subject": "Daily Summary", "body": email_body}
```

---

## ✅ Next Steps

1. **Check terminal** - Look for error messages
2. **Check spam folder** - Email might be filtered
3. **Check automation result** - See what the dashboard says
4. **Try again** - Create a new automation and watch the terminal

---

**Need Help?** Check the terminal output when running automations - it shows detailed debug information!


