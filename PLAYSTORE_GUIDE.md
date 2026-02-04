# How to Publish AI Sales Agent to Google Play Store

Your app is now a **Progressive Web App (PWA)**! Here's how to get it on the Play Store.

---

## Step 1: Deploy to a Public URL (Required)

Before Play Store, you need a live HTTPS URL:

### Option A: Deploy to Render.com (Free)
1. Go to https://render.com and sign up
2. Click "New +" → "Web Service"
3. Connect your GitHub repo (or upload code)
4. Set:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
5. Add environment variables (PayFast keys, SECRET_KEY)
6. Click "Create Web Service"
7. Your app will be at: `https://your-app.onrender.com`

### Option B: Deploy to Railway.app
1. Go to https://railway.app
2. Click "New Project" → "Deploy from GitHub"
3. Add environment variables
4. Done! Get your URL

---

## Step 2: Test PWA Installation

Once deployed, test that PWA works:

1. Open your app URL on **Chrome mobile**
2. You should see "Add to Home Screen" prompt
3. Or tap the 3-dot menu → "Install app"
4. The app should open like a native app (no browser bar)

---

## Step 3: Create Play Store Listing (TWA)

### What is TWA?
**Trusted Web Activity** wraps your PWA in an Android app shell. Users download from Play Store, but it's your web app inside.

### Requirements:
- Google Play Developer account ($25 one-time fee)
- Your deployed PWA URL
- App icons (already created in `/static/icons/`)

### Easy Method: Use PWA Builder

1. Go to https://www.pwabuilder.com
2. Enter your deployed URL
3. Click "Package for stores"
4. Select "Android"
5. It generates an APK/AAB file automatically
6. Download the Android package

### Alternative: Use Bubblewrap CLI

```bash
# Install Bubblewrap
npm install -g @anthropic/bubblewrap-cli

# Initialize your TWA
bubblewrap init --manifest=https://your-app.com/static/manifest.json

# Build the APK
bubblewrap build
```

---

## Step 4: Submit to Play Store

1. Go to https://play.google.com/console
2. Create new app
3. Fill in details:
   - **App name**: AI Sales Agent
   - **Category**: Business
   - **Description**: Automate your sales with AI
4. Upload your AAB file from PWABuilder
5. Add screenshots (from `/static/screenshots/`)
6. Submit for review

---

## Step 5: Digital Asset Links (Required)

For TWA to work, you need to prove you own the domain:

1. Get the SHA-256 fingerprint from your signing key (shown in PWABuilder)
2. Create file at: `https://your-app.com/.well-known/assetlinks.json`

```json
[{
  "relation": ["delegate_permission/common.handle_all_urls"],
  "target": {
    "namespace": "android_app",
    "package_name": "com.yourcompany.aisalesagent",
    "sha256_cert_fingerprints": ["YOUR_SHA256_FROM_PWABUILDER"]
  }
}]
```

I'll add a route for this in your Flask app:

---

## What Users See

| Platform | Experience |
|----------|------------|
| **Play Store** | Download like any app |
| **Phone** | Opens full-screen, no browser bar |
| **Updates** | Automatic (just update your web app!) |
| **Size** | Tiny (~2MB) since it's just a wrapper |

---

## Timeline

1. **Deploy to web**: 30 minutes
2. **Generate TWA package**: 10 minutes  
3. **Play Store review**: 1-7 days

---

## Quick Checklist

- [ ] Deploy app to HTTPS URL
- [ ] Test PWA install on mobile Chrome
- [ ] Create Google Play Developer account ($25)
- [ ] Generate APK with PWABuilder
- [ ] Add assetlinks.json to your server
- [ ] Submit to Play Store
- [ ] Wait for approval

---

**Need help?** The PWABuilder tool at https://www.pwabuilder.com does most of the work automatically!
