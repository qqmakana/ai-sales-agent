# 🧪 Testing Guide - AI Agent Web Platform

## 🚀 Quick Start Testing

### Step 1: Start the App
```powershell
python app.py
```
Then open: `http://localhost:5000`

---

## ✅ Complete Testing Checklist

### 1. **Homepage Testing** (`/`)
- [ ] See pricing cards (Free, Pro, Business)
- [ ] Click "Get Started Free" → Goes to signup
- [ ] Click "Login" → Goes to login page
- [ ] Navigation bar shows at top

### 2. **Sign Up** (`/signup`)
- [ ] Enter email and password
- [ ] Click "Create Account"
- [ ] Should automatically log you in
- [ ] Should redirect to dashboard
- [ ] **Back button**: Click "← Back" or use navbar "Login" link

### 3. **Login** (`/login`)
- [ ] Enter your email and password
- [ ] Click "Login"
- [ ] Should redirect to dashboard
- [ ] **Back button**: Use navbar "Sign Up" link or browser back button

### 4. **Dashboard** (`/dashboard`)
**What to test:**
- [ ] See your email displayed
- [ ] See "Free Plan" badge
- [ ] See "Used 0/10 automations this month"
- [ ] Click "+ Create New Automation" → Goes to create page
- [ ] Click "Upgrade to Pro" → Goes to subscription page
- [ ] See "No automations yet" message (if first time)

**Navigation:**
- [ ] Navbar: "Dashboard" link works
- [ ] Navbar: "Subscription" link works
- [ ] Navbar: "Logout" link works

### 5. **Create Automation** (`/create-automation`)
**What to test:**
- [ ] **Back button**: Click "← Back to Dashboard" → Returns to dashboard
- [ ] Enter goal: "Email Sarah the daily summary"
- [ ] Click "Run Automation"
- [ ] Should redirect back to dashboard
- [ ] Should see success message
- [ ] Automation should appear in "Recent Automations" list
- [ ] Automation status should be "Completed"
- [ ] Should see result message

**Test multiple automations:**
- [ ] Create 2nd automation: "Read daily_todos.txt and send it to makanaiii@outlook.com"
- [ ] Create 3rd automation: "Send email with file content"
- [ ] Check automation count increases (should show "Used 3/10")

**Test free tier limit:**
- [ ] Create 10 automations total
- [ ] Try to create 11th automation
- [ ] Should see error: "You've reached your monthly automation limit"
- [ ] Should redirect to subscription page

### 6. **Subscription Page** (`/subscription`)
**What to test:**
- [ ] **Back button**: Click "← Back to Dashboard" → Returns to dashboard
- [ ] See all 3 pricing cards
- [ ] Free plan shows "Current Plan" (if on free tier)
- [ ] See "Your Current Usage" section
- [ ] See automation count
- [ ] Click "Upgrade to Pro" → (Will add Stripe later, for now just shows button)

**Navigation:**
- [ ] Navbar: "Dashboard" link works
- [ ] Navbar: "Subscription" link works

### 7. **Automation Results**
**What to check:**
- [ ] Automation cards show goal text
- [ ] Status badges show correctly (Pending, Running, Completed, Failed)
- [ ] Result text displays properly
- [ ] Created timestamp shows correctly
- [ ] Multiple automations display in list

---

## 🎯 Key Features to Test

### ✅ Authentication Flow
1. Sign up → Auto-login → Dashboard
2. Logout → Login → Dashboard
3. Try accessing `/dashboard` without login → Should redirect to login

### ✅ Automation Execution
1. Create automation → Agent runs → Result shown
2. Check that your existing agent system works (reads files, sends emails)
3. Verify email was actually sent (check makanaiii@outlook.com inbox)

### ✅ Free Tier Limits
1. Run 10 automations → All should work
2. Run 11th automation → Should block and show upgrade message
3. Check usage counter updates correctly

### ✅ Navigation
- All pages have back buttons or navbar links
- Can navigate between Dashboard, Create Automation, Subscription
- Can logout and login again

---

## 🐛 Common Issues to Check

### If automations don't run:
- Check terminal for errors
- Verify `daily_todos.txt` exists
- Check email credentials in `cli.py` (lines 12-13)

### If database errors:
- Delete `agent_platform.db` file
- Restart app (will recreate database)

### If styling looks broken:
- Check browser console for CSS errors
- Verify `static/style.css` exists

---

## 📊 Expected Results

### After Sign Up:
- User created in database
- Subscription tier: "free"
- Automation count: 0

### After Running Automation:
- Automation record created
- Status: "completed"
- Result text shows agent output
- Automation count increments

### After 10 Automations:
- Automation count: 10
- 11th automation blocked
- Upgrade message shown

---

## 🎨 UI Elements to Verify

- [ ] Buttons are clickable and styled correctly
- [ ] Forms submit properly
- [ ] Flash messages appear (green for success, red for errors)
- [ ] Status badges show correct colors
- [ ] Navigation bar works on all pages
- [ ] Back buttons work
- [ ] Mobile responsive (try resizing browser)

---

## 💰 Monetization Features Tested

- ✅ Free tier limit enforced (10/month)
- ✅ Usage tracking works
- ✅ Upgrade prompts appear
- ✅ Subscription page shows current plan
- ⏳ Stripe integration (next step)

---

## 📝 Test Scenarios

### Scenario 1: New User Journey
1. Visit homepage
2. Sign up
3. Create first automation
4. View result
5. Check subscription page
6. Try to exceed free limit

### Scenario 2: Returning User
1. Login
2. View previous automations
3. Create new automation
4. Logout

### Scenario 3: Free Tier Limit
1. Create 10 automations
2. Try 11th → Should block
3. Go to subscription page
4. See upgrade options

---

## ✅ Success Criteria

The app is working correctly if:
- ✅ You can sign up and login
- ✅ You can create and run automations
- ✅ Automations actually execute (emails sent, files read)
- ✅ Results show in dashboard
- ✅ Free tier limit blocks after 10 automations
- ✅ Navigation works (back buttons, navbar)
- ✅ All pages load without errors

---

**Ready to test?** Start with Step 1 above and work through the checklist!


