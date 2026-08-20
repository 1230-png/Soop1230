# Product Review Channel Setup Guide

## Overview

**Product Review** is an automated YouTube channel that generates professional product reviews and uploads them daily. The channel leverages affiliate marketing to generate revenue through Coupang and Amazon links.

### Channel Statistics
```
📊 Monthly Output:   60-90 videos (Shorts + long-form)
⏰ Upload Schedule:   08:00, 14:00, 20:00 KST (3 times daily)
💰 Revenue Model:    Affiliate commissions + AdSense
🎯 Categories:       Electronics, Home, Fashion, Health
```

### Revenue Potential

```
Product Average:      100,000 won
Affiliate Rate:       7% (Coupang 5-15%, Amazon 5-10%)
Per Sale Value:       7,000 won
Target Sales/Month:   10-30
Estimated Revenue:    70K-210K won/month

Combined (6 months):  420K-1.26M won
```

---

## 1. Prerequisites

### Required APIs (Already Have)
- ✅ **Groq API Key** - Review text generation
- ✅ **ElevenLabs API Key** - Voice narration (optional)
- ✅ **YouTube API** - Video uploads

### New Requirements

#### 🤝 Affiliate Program Accounts
You must enroll in these programs to generate affiliate links:

1. **Coupang Partners** (Korea-specific)
   - Link: https://partners.coupang.com
   - Commission: 5-15% (varies by category)
   - Already have ID? ✅

2. **Amazon Associates** (Global)
   - Link: https://affiliate-program.amazon.com
   - Commission: 5-10%
   - Apply if needed

---

## 2. Configuration

### Step 1: Set Environment Variables

Add to your GitHub Secrets or `.env` file:

```bash
# Already configured
GROQ_API_KEY=your_groq_key
ELEVENLABS_API_KEY=your_elevenlabs_key
YOUTUBE_REFRESH_TOKEN=your_youtube_token
YOUTUBE_CLIENT_ID=your_client_id
YOUTUBE_CLIENT_SECRET=your_client_secret

# NEW: Add your affiliate IDs
COUPANG_AFFILIATE_ID=your_coupang_id
AMAZON_AFFILIATE_ID=your_amazon_id  # Optional
```

### Step 2: Product Data CSV

Create CSV files in `product_review/data/`:

```bash
product_review/data/
├─ products_electronics.csv
├─ products_home.csv
├─ products_fashion.csv
└─ products_health.csv
```

**CSV Format:**
```csv
id,name,category,price,amazon_link,coupang_link,description,image_url,specs
PROD_001,Smart Speaker Pro,electronics,150000,https://amazon.com/dp/B0XXXXX,https://coupang.com/vp/products/XXXXX,AI speaker with smart home control,https://example.com/image.jpg,"[""Voice Control"",""AI"",""Smart Home""]"
```

**Required Fields:**
- `id` - Unique product ID (PROD_XXX)
- `name` - Product name
- `category` - Product category
- `price` - Price in won
- `amazon_link` - Amazon product URL
- `coupang_link` - Coupang product URL
- `description` - Short description
- `image_url` - Product image URL
- `specs` - JSON array of specs (as string)

### Step 3: Add Sample Products

Run to generate sample data:

```bash
python -m product_review.scripts.fetch_products electronics 3
```

---

## 3. How It Works

### Daily Pipeline

```
08:00 KST ──→ Fetch 3-5 products (Electronics)
            ├─ Load from products_electronics.csv
            ├─ Generate reviews using Groq
            ├─ Create video (Shorts + long-form)
            └─ Upload with affiliate links

14:00 KST ──→ Fetch 3-5 products (Home)
            └─ Same pipeline

20:00 KST ──→ Fetch 3-5 products (Fashion)
            └─ Same pipeline
```

### Video Formats

**Shorts (45 seconds)**
- Product image with rating overlay
- No voice narration
- Immediate upload

**Long-form (2 minutes)**
- Product image
- Voice narration of review
- Scheduled 2 hours after Shorts
- More detailed content

### Description Format

All videos include:
```
[Product Name]
⭐ Rating/5.0 | Price: XX,XXX원

【Pros】
✅ Pro 1
✅ Pro 2
✅ Pro 3

【Cons】
❌ Con 1
❌ Con 2

【Buy Links】
🛒 Coupang: [AFFILIATE_LINK]
🛒 Amazon: [AFFILIATE_LINK]

【Disclosure】
This video contains affiliate links. Purchases through 
these links provide us a small commission at no extra 
cost to you. This helps us continue creating reviews.

Subscribe + Enable Notifications for daily reviews!

---
AI-generated product review
```

---

## 4. Testing

### Test Locally

```bash
# 1. Test product fetching
python product_review/scripts/fetch_products.py electronics 1

# 2. Test review generation
python product_review/scripts/fetch_products.py electronics 1 | \
  python product_review/scripts/generate_review.py

# 3. Test video creation
python product_review/scripts/fetch_products.py electronics 1 | \
  python product_review/scripts/generate_review.py | \
  python product_review/scripts/generate_video.py

# 4. Test upload (requires YouTube credentials)
python product_review/scripts/fetch_products.py electronics 1 | \
  python product_review/scripts/generate_review.py | \
  python product_review/scripts/generate_video.py | \
  python product_review/scripts/upload_review.py
```

### Test on GitHub Actions

1. Go to **Actions** tab
2. Select **Product Review Daily**
3. Click **Run workflow**
4. Select a category (electronics, home, fashion)
5. Wait for completion (15-20 minutes)
6. Check upload results in logs

---

## 5. Adding More Products

### Method 1: Manual CSV Entry

Edit `product_review/data/products_electronics.csv`:

```csv
PROD_004,New Product,electronics,50000,https://amazon.com/...,https://coupang.com/...,Description,https://image.url,"[""Spec1"",""Spec2""]"
```

### Method 2: Bulk Import

Create `bulk_import.py`:

```python
import csv
from datetime import datetime

products = [
    # Add your products here
    {
        "id": f"PROD_{i:03d}",
        "name": "Product Name",
        "category": "electronics",
        "price": 100000,
        "amazon_link": "https://...",
        "coupang_link": "https://...",
        "description": "Description",
        "image_url": "https://...",
        "specs": '["Spec1", "Spec2"]'
    }
]

with open("product_review/data/products_electronics.csv", "w") as f:
    writer = csv.DictWriter(f, fieldnames=products[0].keys())
    writer.writeheader()
    writer.writerows(products)
```

---

## 6. Affiliate Link Tracking

### Coupang Partners

Coupang provides automatic tracking. Your affiliate ID is embedded in the URL:

```
https://coupang.com/vp/products/XXXXX?partnerType=affiliate&affiliateId=YOUR_ID
```

**Track Sales:**
1. Log in to https://partners.coupang.com
2. Dashboard → Commission Report
3. View sales/commission by product

### Amazon Associates

Amazon provides a dashboard with tracking:

```
https://amazon.com/dp/B0XXXXX?tag=YOUR_AFFILIATE_ID
```

**Track Sales:**
1. Log in to https://affiliate-program.amazon.com
2. Reports → Earnings
3. View clicks, conversions, earnings

---

## 7. Compliance & Disclosure

### Required Disclosures

✅ **FTC/YouTube Compliance**
- Video descriptions must include affiliate link disclosure
- Already included in `build_description()` function
- "This video contains affiliate links" statement required

✅ **Platform Guidelines**
- Coupang: Requires affiliate ID in URL
- Amazon: Requires proper tag format
- YouTube: Must comply with policy on affiliate links

✅ **Best Practices**
- Be honest in reviews (don't fake positives)
- Disclose cons fairly
- Recommend based on actual product quality
- Don't promote products you haven't researched

---

## 8. Troubleshooting

### "No affiliate link generated"
- Check Coupang Partner ID is set in secrets
- Verify affiliate ID format is correct
- Check if product link is valid

### "Reviews look generic"
- Verify Groq API key is valid
- Check product specs are detailed in CSV
- Try increasing Groq temperature (0.7 default)

### "Videos not uploading"
- Check YouTube refresh token is valid
- Verify API quotas not exceeded
- Check video files are MP4 format

### "Product image not found"
- Fallback creates placeholder image automatically
- Or provide valid image_url in CSV
- Check image URL is publicly accessible

---

## 9. Performance Optimization

### Reduce Processing Time

**Current:** ~15-20 minutes per 3 products

```bash
# Parallel processing (if needed)
# Split products across multiple GitHub Actions
# Update matrix in workflow file:
strategy:
  matrix:
    category: [electronics, home, fashion, health]
    batch: [1, 2, 3]
```

### Reduce API Costs

**Current:** Free tier sufficient for 3-5 products/day

```bash
# Groq: 30 calls/day free
# ElevenLabs: 100K chars/month (≈ 5 long-form videos/day)
# YouTube: 10K quota units/day
```

---

## 10. Next Steps

### Week 1: Setup
- [ ] Add Coupang Partner ID to secrets
- [ ] Create products CSV files (10-20 products each)
- [ ] Test workflow manually (1 run)
- [ ] Verify first uploads to YouTube

### Week 2-4: Monitoring
- [ ] Track daily uploads
- [ ] Monitor affiliate sales
- [ ] Adjust product selection based on performance
- [ ] Add more products to CSV

### Month 2: Expansion
- [ ] Add health/beauty category
- [ ] Enroll in Amazon Associates
- [ ] A/B test video lengths
- [ ] Analyze top-performing products

### Month 3: Optimization
- [ ] Generate custom thumbnails
- [ ] Add trending products
- [ ] Optimize affiliate links
- [ ] Expand to 4-5 products per run

---

## 11. FAQ

**Q: How much can I earn?**
- A: Depends on clicks and conversions. Typical: 10-30 sales/month = 70K-210K won. Can scale with more products.

**Q: Do I need to create products?**
- A: No. Use existing products from Coupang/Amazon. Just need links and descriptions.

**Q: Can I use affiliate links from other platforms?**
- A: Yes, but Coupang/Amazon are recommended (highest commission + easy tracking).

**Q: Is this legal/ethical?**
- A: Yes, as long as you disclose affiliate links (already done). Be honest in reviews.

**Q: How do I get more views?**
- A: Add trending products, optimize titles, use trending tags, engage with comments.

**Q: Can I monetize without AdSense?**
- A: Yes! Affiliate commissions are your primary revenue (60-70% of income).

---

## 12. Resources

- 📖 [Coupang Partners Guide](https://partners.coupang.com/guide)
- 📖 [Amazon Associates Manual](https://affiliate-program.amazon.com/help)
- 📖 [YouTube Affiliate Policy](https://support.google.com/youtube/answer/9047208)
- 🛠️ [Groq API Docs](https://console.groq.com/docs)
- 🛠️ [ElevenLabs Docs](https://docs.elevenlabs.io)
- 🛠️ [YouTube API Docs](https://developers.google.com/youtube/v3)

---

**Status**: ✅ Ready to deploy

**Next**: Add Coupang ID to GitHub Secrets, then run your first test!
