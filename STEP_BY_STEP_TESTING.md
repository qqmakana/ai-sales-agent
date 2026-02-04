# 🧪 Step-by-Step Testing Guide

## How to Test Each Functionality

---

## ✅ Test 1: Dashboard Display

### Steps:
1. **Login** (if not already logged in)
   - Go to: `http://localhost:5000`
   - Click "Login"
   - Email: `q@q.com`
   - Password: `q`
   - Click "Login"

2. **Check Dashboard Elements:**
   - [ ] See "Welcome, q@q.com" at top
   - [ ] See "Free Plan" badge (blue pill)
   - [ ] See "Used X/10 automations this month"
   - [ ] See "+ Create New Automation" button (purple)
   - [ ] See "Upgrade to Pro" button (gray)
   - [ ] See "Recent Automations" section

### Expected Result:
- All elements visible
- No errors on page
- Navigation bar shows at top

---

## ✅ Test 2: Create Automation

### Steps:
1. **Go to Create Page:**
   - Click "+ Create New Automation" button
   - Should go to `/create-automation` page

2. **Fill Form:**
   - See text area with label "What do you want to automate?"
   - Type: `Email Sarah the daily summary`
   - See example automations below form

3. **Submit:**
   - Click "Run Automation" button (purple)
   - Should redirect back to dashboard
   - Should see flash message (green success or red error)

### Expected Result:
- Form submits successfully
- Redirects to dashboard
- Success/error message appears

---

## ✅ Test 3: Automation Execution

### Steps:
1. **After Creating Automation:**
   - Look at dashboard
   - Find "Recent Automations" section

2. **Check Automation Card:**
   - [ ] See new automation card
   - [ ] Title shows: "Email Sarah the daily summary"
   - [ ] Status badge shows: "Completed" (green) or "Failed" (red)
   - [ ] See "Created: [date] [time]"
   - [ ] See "Result: [message]" section

3. **Check Automation Count:**
   - [ ] Top right shows "Used 1/10" (or higher number)
   - [ ] Number increases after each automation

### Expected Result:
- Automation appears in list
- Status shows correctly
- Result text displays
- Count increments

---

## ✅ Test 4: Email Sending

### Steps:
1. **Check Automation Result:**
   - Look at automation card in dashboard
   - Read the "Result" section
   - Should say: "Email sent successfully to makanaiii@outlook.com" OR show error

2. **Check Email Inbox:**
   - Open Outlook
   - Login to: `makanaiii@outlook.com`
   - Check Inbox folder
   - Check Spam/Junk folder
   - Look for email from: `sandtonstreets@gmail.com`
   - Subject: "Daily Summary"

3. **Check Terminal Output:**
   - Look at terminal where `app.py` is running
   - Should see debug messages:
     - `[DEBUG] Email password check: password_length=16`
     - `[DEBUG] Sending email with body length: XXX`
     - `[DEBUG] Tool: send_email, Status: ...`

### Expected Result:
- Email arrives in inbox (or spam)
- Email contains file content from `daily_todos.txt`
- Terminal shows email was sent

### If Email Not Received:
- Check spam folder
- Check terminal for errors
- Verify email credentials in `cli.py` (lines 12-13)

---

## ✅ Test 5: Free Tier Limit

### Steps:
1. **Create Multiple Automations:**
   - Create automation #1: "Email Sarah the daily summary"
   - Create automation #2: "Read daily_todos.txt"
   - Create automation #3: "Send email to team"
   - Continue until you have 10 automations

2. **Check Count:**
   - Dashboard should show "Used 10/10 automations"
   - All 10 automations should work

3. **Test Limit:**
   - Try to create 11th automation
   - Enter any goal
   - Click "Run Automation"

4. **Verify Block:**
   - [ ] Should see red error message: "You've reached your monthly automation limit"
   - [ ] Should redirect to subscription page
   - [ ] Automation should NOT be created

### Expected Result:
- First 10 automations work
- 11th automation is blocked
- Upgrade message appears
- Redirects to subscription page

---

## ✅ Test 6: Subscription Page

### Steps:
1. **Go to Subscription Page:**
   - Click "Upgrade to Pro" button OR
   - Click "Subscription" in navbar

2. **Check Pricing Cards:**
   - [ ] See 3 pricing cards: Free, Pro, Business
   - [ ] Free card shows "Current Plan" (if on free tier)
   - [ ] Pro card shows "Upgrade to Pro" button
   - [ ] Business card shows "Upgrade to Business" button

3. **Check Usage Stats:**
   - [ ] See "Your Current Usage" section
   - [ ] See "Plan: Free"
   - [ ] See "Automations this month: X/10"

4. **Test Buttons:**
   - [ ] Buttons are visible
   - [ ] Can click them (will add Stripe later)

### Expected Result:
- All pricing cards display
- Current plan highlighted
- Usage stats show correctly
- Buttons visible (payment integration pending)

---

## ✅ Test 7: Navigation

### Steps:
1. **Test Navbar Links:**
   - [ ] Click "Dashboard" → Goes to dashboard
   - [ ] Click "Subscription" → Goes to subscription page
   - [ ] Click "Logout" → Logs out, goes to homepage

2. **Test Back Buttons:**
   - [ ] On Create Automation page: Click "← Back to Dashboard" → Returns to dashboard
   - [ ] On Subscription page: Click "← Back to Dashboard" → Returns to dashboard

3. **Test Browser Navigation:**
   - [ ] Browser back button works
   - [ ] Can navigate between pages smoothly

### Expected Result:
- All links work
- Back buttons work
- Smooth navigation

---

## 🎯 Complete Test Sequence

### Full Flow Test:
1. **Login** → Dashboard
2. **Create Automation** → "Email Sarah the daily summary"
3. **Check Result** → See automation in dashboard
4. **Check Email** → Verify email was sent
5. **Create 9 More** → Test free tier limit
6. **Try 11th** → Should be blocked
7. **Go to Subscription** → See upgrade options
8. **Logout** → Return to homepage

---

## 📊 What to Report

After testing, tell me:
1. ✅ What worked?
2. ❌ What didn't work?
3. ⚠️ Any errors you saw?
4. 📧 Did email arrive?

---

## 🐛 Troubleshooting

### If automation doesn't run:
- Check terminal for errors
- Check browser console (F12)
- Verify `daily_todos.txt` exists

### If email doesn't send:
- Check terminal output
- Verify Gmail password in `cli.py`
- Check spam folder

### If page doesn't load:
- Check if `app.py` is running
- Check terminal for errors
- Try refreshing page

---

**Start Testing:** Begin with Test 1 and work through each one!
