# Smart Email Pro — Gmail Spam Detector
### Automatically detect & delete spam from YOUR real Gmail using ML + NLP

---

## Project Structure

```
smart_email_pro/
├── ml_model/
│   ├── train_model.py        ← Train Naive Bayes classifier
│   ├── spam_model.pkl        ← Auto-generated after training
│   └── model_stats.pkl       ← Accuracy, precision, F1 stats
│
├── backend/
│   └── app.py                ← Flask API + Gmail OAuth2
│
├── frontend/
│   ├── templates/
│   │   ├── login.html        ← Google Sign-In page
│   │   └── index.html        ← Main dashboard
│   └── static/
│       ├── css/style.css
│       └── js/app.js
│
├── credentials.json          ← YOU MUST ADD THIS (Step 1 below)
├── requirements.txt
└── README.md
```

---

## STEP 1 — Google Cloud Setup (One Time Only, ~15 mins)

### 1.1 Create a Google Cloud Project
1. Go to → https://console.cloud.google.com
2. Click **"New Project"**
3. Name it: `SmartEmailPro` → Click **Create**

### 1.2 Enable Gmail API
1. Go to → **APIs & Services → Library**
2. Search `Gmail API` → Click it → Click **Enable**

### 1.3 Create OAuth2 Credentials
1. Go to → **APIs & Services → Credentials**
2. Click **+ Create Credentials → OAuth Client ID**
3. If asked, set up **OAuth Consent Screen** first:
   - User Type: **External**
   - App name: `Smart Email Pro`
   - Add your Gmail as test user
   - Save
4. Back to Create Credentials:
   - Application type: **Web Application**
   - Name: `Smart Email Pro`
   - Authorized redirect URIs → Add:
     ```
     http://127.0.0.1:5000/oauth2callback
     ```
   - Click **Create**
5. Click **Download JSON**
6. Rename the downloaded file to: `credentials.json`
7. Place it in the **root of this project folder** (same level as requirements.txt)

---

## STEP 2 — Install Dependencies

Open terminal in the project folder:

```bash
pip install -r requirements.txt
```

---

## STEP 3 — Train the ML Model

```bash
python ml_model/train_model.py
```

Output:
```
Accuracy  : 97.80%
Precision : 96.40%
Recall    : 98.10%
F1 Score  : 97.20%
[OK] Model saved → ml_model/spam_model.pkl
```

**Optional (Better Accuracy):**
Download SMS Spam Collection from Kaggle:
→ https://www.kaggle.com/datasets/uciml/sms-spam-collection-dataset
Place `spam.csv` in `ml_model/` folder, then re-run train_model.py

---

## STEP 4 — Run the App

```bash
python backend/app.py
```

---

## STEP 5 — Open in Browser

```
http://127.0.0.1:5000
```

1. You will see the **Sign in with Google** page
2. Click it → Google login screen opens
3. Sign in with your Gmail account
4. Grant permission (Read + Modify Gmail)
5. You are redirected to the **dashboard**
6. Your real Gmail inbox loads with ML spam detection!

---

## How It Works

```
Your Gmail Inbox
      ↓
Gmail API (fetches last 40 emails)
      ↓
Naive Bayes + TF-IDF ML Model
      ↓
Spam (≥50%) → shown with red SPAM badge + confidence %
Ham  (<50%) → shown with green HAM badge
      ↓
Click "Delete All Spam" → Gmail API moves them to Trash
      ↓
Spam stored in Gmail Trash (restorable anytime)
```

---

## Features

| Feature | Description |
|---------|-------------|
| Google OAuth2 Login | Real Gmail sign-in, no password stored |
| Real Gmail Fetch | Reads your actual inbox via Gmail API |
| ML Classification | Naive Bayes + TF-IDF on every email |
| Confidence Score | Visual % bar per email |
| Filter View | All / Spam Only / Safe Only |
| One-Click Delete | Trash all ML-detected spam at once |
| Restore | Untrash any email from Trash folder |
| ML Analytics | Accuracy, Precision, Recall, F1 metrics |
| Logout | Clear session securely |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Login page |
| GET | `/login` | Start Google OAuth2 |
| GET | `/oauth2callback` | Google callback |
| GET | `/logout` | Clear session |
| GET | `/dashboard` | Main dashboard |
| GET | `/api/emails?folder=inbox` | Fetch + classify Gmail emails |
| POST | `/api/emails/<id>/trash` | Move to Gmail Trash |
| POST | `/api/emails/<id>/restore` | Restore from Trash |
| POST | `/api/spam/delete-all` | Trash all detected spam |
| GET | `/api/stats` | ML model performance |
| POST | `/api/classify` | Classify any text |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| ML Model | Naive Bayes + TF-IDF (scikit-learn) |
| Backend | Python + Flask |
| Gmail Integration | Google Gmail API v1 + OAuth2 |
| Frontend | HTML + CSS + Vanilla JS |
| Auth | Google OAuth 2.0 |

---

## Troubleshooting

**"credentials.json not found"**
→ Follow Step 1 above to download it from Google Cloud Console

**"redirect_uri_mismatch" error**
→ Make sure you added `http://127.0.0.1:5000/oauth2callback` in Google Cloud credentials

**"Model not loaded"**
→ Run `python ml_model/train_model.py` first

**Gmail shows "App not verified"**
→ Click "Advanced" → "Go to Smart Email Pro (unsafe)" — this is normal for dev apps

---

Smart Email Pro — ML/NLP Final Year Project
# smart-email-pro
