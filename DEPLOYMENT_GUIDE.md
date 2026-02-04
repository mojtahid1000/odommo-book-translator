# অদম্য প্রেস — Book Translator Deployment Guide

## 🎯 Two Options Available

| Option | Best For | Cost | Setup Time |
|--------|----------|------|-----------|
| **Option A: Streamlit Cloud** | Team web access (URL link) | FREE hosting + API cost | 15 min |
| **Option B: Claude Code** | Developer/personal use | Claude Pro + API cost | 5 min |

---

## ✅ OPTION A: Deploy Web App on Streamlit Cloud (RECOMMENDED)

Your team gets a URL like `https://odommo-translator.streamlit.app` — anyone can upload PDF and download Bangla DOCX from any browser.

### Step 1: Create GitHub Account (if you don't have one)
Go to https://github.com and sign up.

### Step 2: Create a New Repository

1. Go to https://github.com/new
2. Repository name: `odommo-book-translator`
3. Select **Public**
4. Click **Create repository**

### Step 3: Upload Files to GitHub

Upload these 3 files from the `book-translator-cloud` folder to your GitHub repo:

```
app.py
requirements.txt
.streamlit/config.toml
```

**How to upload:**
1. In your new repo, click **"Add file"** → **"Upload files"**
2. Drag and drop `app.py` and `requirements.txt`
3. Click **"Commit changes"**
4. Then create a folder: Click **"Add file"** → **"Create new file"**
5. Type `.streamlit/config.toml` as filename
6. Paste the config.toml content
7. Click **"Commit changes"**

### Step 4: Deploy on Streamlit Cloud

1. Go to https://share.streamlit.io
2. Sign in with your GitHub account
3. Click **"New app"**
4. Select your repo: `odommo-book-translator`
5. Main file: `app.py`
6. Click **"Deploy"**
7. Wait 2-3 minutes for deployment

### Step 5: Share with Your Team

Your app is now live at: `https://[your-username]-odommo-book-translator.streamlit.app`

Share this URL with your team. They just need:
- The URL
- An Anthropic API key (enter in the sidebar)

---

### 🔐 Optional: Pre-set API Key (so team doesn't need to enter it)

In Streamlit Cloud dashboard:
1. Click your app → **Settings** → **Secrets**
2. Add: `ANTHROPIC_API_KEY = "sk-ant-api03-..."`
3. The app will auto-use this key

---

## ✅ OPTION B: Use Claude Code (Developer Option)

Claude Code is a command-line AI tool. Your team member opens terminal, pastes one prompt, and Claude Code does everything.

### Step 1: Install Claude Code

```bash
npm install -g @anthropic-ai/claude-code
```

(Requires Node.js 18+. Install Node.js from https://nodejs.org if needed)

### Step 2: Set API Key

```bash
export ANTHROPIC_API_KEY="sk-ant-api03-..."
```

### Step 3: Run Claude Code

```bash
claude
```

### Step 4: Paste This Prompt

Copy and paste this ENTIRE prompt into Claude Code:

---

````
আমি একটি English PDF বই Bangla-তে translate করতে চাই। নিচের steps follow করো:

1. প্রথমে pip install pymupdf python-docx দিয়ে dependencies install করো

2. আমার PDF file path: [এখানে আপনার PDF এর path দিন, যেমন: /home/user/Downloads/mybook.pdf]

3. প্রতিটি page extract করো এবং নিচের translation rules follow করে Bangla-তে translate করো:

TRANSLATION RULES:
- Reader-Friendly style: English terms রাখো যেগুলো commonly understood (Focus, Energy, Goal, Mindset, Confidence, Productivity, Resilience, Motivation, Discipline, etc.)
- Bangla ব্যবহার করো sentence structure, verbs (করুন, বুঝুন, তৈরি করুন), connectors, everyday words-এ
- কঠিন Bangla avoid করো: "Distraction" ব্যবহার করো "বিক্ষিপ্ততা" নয়, "Resilience" ব্যবহার করো "স্থিতিস্থাপকতা" নয়
- Bangla numerals ব্যবহার করো: ১ ২ ৩ ৪ ৫ ৬ ৭ ৮ ৯ ০
- প্রতিটি chapter-এর heading Bangla-তে translate করো, নিচে English heading parenthesis-এ দাও
- Quotes italic-এ Bangla translate করো
- Numbered items bold heading + description format-এ রাখো

4. সব translated content একটি formatted .docx file-এ save করো:
- Font: Noto Sans Bengali
- Chapter headings: 16pt, bold, centered
- Body: 11pt
- Proper page breaks between chapters
- Header: "বাংলা অনুবাদ" (right aligned, gray)
- Footer: "অদম্য প্রেস" (centered, gray)
- শেষে "— সমাপ্ত —" page দাও

5. Output file save করো: [এখানে output path দিন, যেমন: /home/user/Desktop/bangla_translation.docx]

10 pages করে batch-এ কাজ করো। প্রতি batch-এর পর progress দেখাও।
````

---

### Step 5: Wait and Download

Claude Code will:
1. Install dependencies
2. Extract PDF pages
3. Translate each page
4. Build formatted DOCX
5. Save to your specified path

---

## 💰 API Key Setup (Required for Both Options)

### Get Your API Key:

1. Go to https://console.anthropic.com
2. Sign up / Sign in
3. Go to **Settings** → **API Keys**
4. Click **"Create Key"**
5. Copy the key (starts with `sk-ant-`)

### Add Credits:

1. In console.anthropic.com, go to **Billing**
2. Add $5-10 credit (enough for 2-5 books)
3. Set a spending limit for safety

### For Team Members:

Create separate API keys for each team member:
1. Console → **API Keys** → **Create Key**
2. Name it: "Team-[Name]-BookTranslator"
3. Share the key securely (not over public chat)

---

## 📊 Cost Comparison

| Method | Cost per Book | Setup Time | Team Access |
|--------|--------------|-----------|-------------|
| Streamlit Cloud + Sonnet | ~$2-5 + FREE hosting | 15 min once | ✅ URL link |
| Streamlit Cloud + Haiku | ~$0.30-1.50 + FREE hosting | 15 min once | ✅ URL link |
| Claude Code + Sonnet | ~$2-5 | 5 min each time | ❌ Individual |
| Manual Claude Chat | Free (Pro plan) | 2-3 hours each | ❌ Only you |

---

## 🔧 Troubleshooting

**"Module not found" error** → Run: `pip install anthropic pymupdf python-docx`

**"Authentication error"** → Check your API key is correct and has credits

**"Rate limit" error** → Wait 60 seconds and try again, or reduce batch size

**Streamlit app not loading** → Check GitHub repo has all 3 files (app.py, requirements.txt, .streamlit/config.toml)

**Poor translation quality** → Use Sonnet model and reduce batch size to 3

---

Built for অদম্য প্রেস | Online Tech Academy | Mentor Mojtahidul Islam
