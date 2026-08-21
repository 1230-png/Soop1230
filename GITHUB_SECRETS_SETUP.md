# GitHub Secrets Setup Guide

## 🎯 Overview

All 4 automated channels (AI Stories, Growth Tips, News Summary, Product Review) require API keys stored as **GitHub Secrets**. This guide shows you exactly how to set them up.

---

## 📋 Required Secrets (9 Total)

| Secret Name | Required | Source | Status |
|---|---|---|---|
| `GROQ_API_KEY` | ✅ | https://console.groq.com | ✅ Have |
| `ELEVENLABS_API_KEY` | ✅ | https://elevenlabs.io | ✅ Have |
| `PEXELS_API_KEY` | ⏳ | https://pexels.com/developers | ⏳ Need |
| `NEWSAPI_KEY` | ⏳ | https://newsapi.org | ⏳ Need |
| `YOUTUBE_CLIENT_ID` | ✅ | Google Cloud Console | ✅ Have |
| `YOUTUBE_CLIENT_SECRET` | ✅ | Google Cloud Console | ✅ Have |
| `YOUTUBE_REFRESH_TOKEN` | ✅ | Google Cloud Console (OAuth) | ✅ Have |
| `COUPANG_AFFILIATE_ID` | ✅ | https://partners.coupang.com | ✅ Have |
| `AMAZON_AFFILIATE_ID` | ⏳ | https://affiliate-program.amazon.com | ⏳ Optional |

---

## 🚀 How to Add GitHub Secrets

### Step 1: Go to GitHub Repository Settings

1. Open your repository: https://github.com/1230-png/Soop1230
2. Click **Settings** (top menu)
3. Click **Secrets and variables** → **Actions** (left menu)
4. You should see a section for "Repository secrets"

### Step 2: Click "New repository secret" Button

A form will appear with two fields:
- **Name**: Secret name (e.g., `GROQ_API_KEY`)
- **Secret**: Secret value (e.g., your actual API key)

### Step 3: Add Each Secret One by One

---

## 📝 Adding Each Secret

### 1. GROQ_API_KEY ✅

**You already have this**

```
Name: GROQ_API_KEY
Secret: [your_groq_key_from_console.groq.com]
```

If you don't have it:
1. Go to https://console.groq.com
2. Click API Keys
3. Create new key if needed
4. Copy and paste value

---

### 2. ELEVENLABS_API_KEY ✅

**You already have this:** `94b1cb7238be0b836d67075dabd806d53a1fee98ae43f59e3c125838fb7ab4dc`

```
Name: ELEVENLABS_API_KEY
Secret: 94b1cb7238be0b836d67075dabd806d53a1fee98ae43f59e3c125838fb7ab4dc
```

---

### 3. YOUTUBE_CLIENT_ID ✅

**You already have this from Google Cloud Console**

```
Name: YOUTUBE_CLIENT_ID
Secret: [your_client_id_from_google_cloud_console]
```

Where to find it:
1. Go to https://console.cloud.google.com
2. Select your project
3. Go to Credentials (left menu)
4. Find "Desktop application" credential
5. Copy "Client ID" value

---

### 4. YOUTUBE_CLIENT_SECRET ✅

**You already have this from Google Cloud Console**

```
Name: YOUTUBE_CLIENT_SECRET
Secret: [your_client_secret_from_google_cloud_console]
```

Where to find it:
1. Go to https://console.cloud.google.com
2. Select your project
3. Go to Credentials (left menu)
4. Find "Desktop application" credential
5. Copy "Client secret" value

---

### 5. YOUTUBE_REFRESH_TOKEN ✅

**This is the critical one** - Generate using OAuth flow

#### Option A: Use Existing Login (Recommended)

If you have existing YouTube login credentials:

1. Go to Google Account: https://myaccount.google.com
2. Click "Security" (left menu)
3. Scroll to "Your devices" → "Manage all devices"
4. Find any device with YouTube login history
5. Look for stored OAuth tokens

If you find a stored token:
```
Name: YOUTUBE_REFRESH_TOKEN
Secret: [your_refresh_token]
```

#### Option B: Generate New Token via OAuth

If you need to generate a new token:

1. Go to https://console.cloud.google.com
2. Select your project
3. Create a new Desktop application credential if needed
4. Set Authorized JavaScript origins: `http://localhost:8080`
5. Set Authorized redirect URIs: `http://localhost:8080/`

Then run this Python script locally:

```python
#!/usr/bin/env python3
import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/youtube"]

def get_refresh_token():
    """Generate YouTube refresh token"""
    
    # Download your credentials JSON from Google Cloud Console
    # Save as credentials.json in current directory
    
    flow = InstalledAppFlow.from_client_secrets_file(
        'credentials.json', 
        SCOPES
    )
    
    # This opens a browser for authentication
    creds = flow.run_local_server(port=8080)
    
    # Print the refresh token
    print(f"YOUTUBE_REFRESH_TOKEN: {creds.refresh_token}")
    
    # Also save to file for backup
    with open('youtube_token.txt', 'w') as f:
        f.write(creds.refresh_token)

if __name__ == '__main__':
    get_refresh_token()
```

**How to use:**
1. Download credentials JSON from Google Cloud Console (in Credentials page)
2. Save it as `credentials.json` in a folder
3. Copy the Python script above
4. Run: `python get_token.py`
5. Browser opens → Log in with YouTube account
6. Copy the printed refresh token

Then add to GitHub Secrets:
```
Name: YOUTUBE_REFRESH_TOKEN
Secret: [the_refresh_token_from_script]
```

---

### 6. COUPANG_AFFILIATE_ID ✅

**You already have this**

```
Name: COUPANG_AFFILIATE_ID
Secret: [your_coupang_id_from_partners.coupang.com]
```

Where to find it:
1. Go to https://partners.coupang.com
2. Log in with your account
3. Dashboard → Manage Account → Affiliate ID
4. Copy your ID (looks like: `sd12345abc`)

---

### 7. PEXELS_API_KEY ⏳

Required for **News Summary** channel (background videos)

```
Name: PEXELS_API_KEY
Secret: [your_pexels_api_key]
```

Where to get it:
1. Go to https://pexels.com/developers
2. Click "Generate API Key"
3. Copy the key
4. Add to GitHub Secrets

---

### 8. NEWSAPI_KEY ⏳

Required for **News Summary** channel (news content)

```
Name: NEWSAPI_KEY
Secret: [your_newsapi_key]
```

Where to get it:
1. Go to https://newsapi.org
2. Sign up (free tier available)
3. Copy your API key
4. Add to GitHub Secrets

---

### 9. AMAZON_AFFILIATE_ID ⏳ (Optional)

Not required, but recommended for **Product Review** channel

```
Name: AMAZON_AFFILIATE_ID
Secret: [your_amazon_affiliate_id]
```

Where to get it:
1. Go to https://affiliate-program.amazon.com
2. Log in or sign up
3. Go to "Account Settings" → "Tracking ID"
4. Copy your Associate ID (looks like: `sootest-20`)
5. Add to GitHub Secrets

---

## ✅ Verification Checklist

After adding all secrets, verify they're set correctly:

```bash
# From your local terminal
cd /path/to/Soop1230

# Check which secrets are recognized by Actions
# (You can't see the values, but you can verify names)
# Go to: https://github.com/1230-png/Soop1230/settings/secrets/actions

# Should see:
✅ GROQ_API_KEY
✅ ELEVENLABS_API_KEY
✅ YOUTUBE_CLIENT_ID
✅ YOUTUBE_CLIENT_SECRET
✅ YOUTUBE_REFRESH_TOKEN
✅ COUPANG_AFFILIATE_ID
✅ PEXELS_API_KEY
✅ NEWSAPI_KEY
⏳ AMAZON_AFFILIATE_ID (optional)
```

---

## 🧪 Test Each Channel

Once all secrets are added, test the workflows:

### Test 1: AI Stories Daily
1. Go to **Actions** tab
2. Select **AI Stories Daily**
3. Click **Run workflow** → **Run workflow**
4. Wait 5-10 minutes
5. Check job logs for success

### Test 2: Growth Tips Daily
1. Go to **Actions** tab
2. Select **Growth Tips Daily**
3. Click **Run workflow** → **Run workflow**
4. Wait 10-15 minutes
5. Check job logs for success

### Test 3: News Summary Daily
1. Go to **Actions** tab
2. Select **News Summary Daily**
3. Click **Run workflow** → **Run workflow**
4. Wait 15-20 minutes
5. Check job logs for success

### Test 4: Product Review Daily
1. Go to **Actions** tab
2. Select **Product Review Daily**
3. Click **Run workflow** → select category → **Run workflow**
4. Wait 15-20 minutes
5. Check job logs for success
6. Verify video uploaded to YouTube channel

---

## 🔑 Where to Get Each API Key

| Service | Link | Free Tier | Time to Get |
|---|---|---|---|
| Groq | https://console.groq.com | 30 calls/day | 2 min ✅ |
| ElevenLabs | https://elevenlabs.io | 100K chars/month | 2 min ✅ |
| Pexels | https://pexels.com/developers | Unlimited | 2 min |
| NewsAPI | https://newsapi.org | 100/day | 2 min |
| YouTube OAuth | https://console.cloud.google.com | Unlimited | 5 min ✅ |
| Coupang Affiliate | https://partners.coupang.com | Unlimited | Already have ✅ |
| Amazon Affiliate | https://affiliate-program.amazon.com | Unlimited | Optional |

**Total time needed:** ~10-15 minutes for all missing keys

---

## ❌ Troubleshooting

### "Workflow failed: Missing secret GROQ_API_KEY"
- Go to GitHub repo → Settings → Secrets
- Verify the secret exists
- Check the exact name matches

### "401 Unauthorized on YouTube upload"
- Verify YOUTUBE_REFRESH_TOKEN is valid
- If expired, regenerate new token (see Option B above)
- Check YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET match

### "API rate limit exceeded"
- Free tier limits:
  - Groq: 30 calls/day (usually OK)
  - ElevenLabs: 100K chars/month (usually OK)
  - NewsAPI: 100 requests/day (usually OK)
  - YouTube: 10K quota units/day (usually OK)
- If exceeded, wait for next day or upgrade plan

### "News API returns no results"
- Some countries/news categories need API subscription
- Downgrade to top-level news only
- Or switch to different news source

---

## 📋 Quick Checklist

- [ ] Go to GitHub repo Settings → Secrets → Actions
- [ ] Add GROQ_API_KEY
- [ ] Add ELEVENLABS_API_KEY
- [ ] Add YOUTUBE_CLIENT_ID
- [ ] Add YOUTUBE_CLIENT_SECRET
- [ ] Add YOUTUBE_REFRESH_TOKEN ⭐ (most important)
- [ ] Add COUPANG_AFFILIATE_ID
- [ ] Add PEXELS_API_KEY (for News Summary)
- [ ] Add NEWSAPI_KEY (for News Summary)
- [ ] (Optional) Add AMAZON_AFFILIATE_ID
- [ ] Run test on Product Review workflow
- [ ] Verify video uploaded to YouTube

---

## 🎬 Next Steps

1. **Get missing API keys** (5-10 minutes)
2. **Add all secrets to GitHub** (3-5 minutes)
3. **Test Product Review workflow** (15-20 minutes)
4. **Verify YouTube upload** (1 minute)
5. **Enable scheduled runs** (1 minute)

**Total: ~25 minutes to full automation! 🚀**

---

**Status**: ⏳ Ready to add secrets

**Your next action**: Go to https://github.com/1230-png/Soop1230/settings/secrets/actions and start adding secrets!
