"""
app.py — Smart Email Pro Backend
Gmail OAuth2 + ML Spam Detection + Auto-Delete to Trash

Endpoints:
  GET  /                          → Login page
  GET  /dashboard                 → Main dashboard (after login)
  GET  /login                     → Start Google OAuth2 flow
  GET  /oauth2callback            → Google OAuth2 callback
  GET  /logout                    → Clear session
  GET  /api/emails                → Fetch & classify Gmail emails
  POST /api/emails/<id>/trash     → Move single email to Gmail Trash
  POST /api/emails/<id>/restore   → Remove from trash (restore)
  POST /api/spam/delete-all       → Trash all detected spam
  GET  /api/stats                 → ML model stats
  POST /api/classify              → Classify any text
"""

import os, pickle, json
from flask import Flask, redirect, request, session, jsonify, render_template, url_for
from flask_cors import CORS
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import google.auth.transport.requests
import base64, email as email_lib
from email.header import decode_header

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
ML_DIR      = os.path.join(BASE_DIR, "..", "ml_model")
MODEL_PATH  = os.path.join(ML_DIR, "spam_model.pkl")
STATS_PATH  = os.path.join(ML_DIR, "model_stats.pkl")
TMPL_DIR    = os.path.join(BASE_DIR, "..", "frontend", "templates")
STATIC_DIR  = os.path.join(BASE_DIR, "..", "frontend", "static")
CRED_PATH   = os.path.join(BASE_DIR, "..", "credentials.json")

# ── Flask ──────────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder=TMPL_DIR, static_folder=STATIC_DIR)
app.secret_key = os.urandom(24)
CORS(app)

# Allow HTTP for local dev (remove in production)
if os.environ.get("FLASK_ENV") != "production":
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid"
]

SPAM_THRESHOLD       = 0.50
AUTO_TRASH_THRESHOLD = 0.85

# ── Load ML Model ──────────────────────────────────────────────────────────
pipeline    = None
model_stats = {}

def load_model():
    global pipeline, model_stats
    if os.path.exists(MODEL_PATH):
        with open(MODEL_PATH, "rb") as f:
            pipeline = pickle.load(f)
        if os.path.exists(STATS_PATH):
            with open(STATS_PATH, "rb") as f:
                model_stats = pickle.load(f)
        print("[OK] ML model loaded.")
    else:
        print("[WARN] Model not found. Run: python ml_model/train_model.py")

load_model()

# ── Helpers ────────────────────────────────────────────────────────────────
def classify(subject, body):
    if pipeline is None:
        return {"label": "unknown", "confidence": 0.0, "is_spam": False}
    text  = (subject + " " + body).strip()
    proba = float(pipeline.predict_proba([text])[0][1])
    return {
        "label":      "spam" if proba >= SPAM_THRESHOLD else "ham",
        "confidence": round(proba, 4),
        "is_spam":    proba >= SPAM_THRESHOLD
    }

def decode_str(s):
    """Decode email header string."""
    if not s:
        return ""
    parts = decode_header(s)
    result = ""
    for part, enc in parts:
        if isinstance(part, bytes):
            result += part.decode(enc or "utf-8", errors="replace")
        else:
            result += str(part)
    return result

def get_body(msg):
    """Extract plain text body from email message."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in cd:
                try:
                    body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                    break
                except:
                    pass
    else:
        try:
            body = msg.get_payload(decode=True).decode("utf-8", errors="replace")
        except:
            pass
    return body[:500]  # limit to 500 chars for classification

def get_gmail_service():
    """Build Gmail API service from session credentials."""
    creds_data = session.get("credentials")
    if not creds_data:
        return None
    creds = Credentials(
        token=creds_data["token"],
        refresh_token=creds_data.get("refresh_token"),
        token_uri=creds_data["token_uri"],
        client_id=creds_data["client_id"],
        client_secret=creds_data["client_secret"],
        scopes=creds_data["scopes"]
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(google.auth.transport.requests.Request())
        session["credentials"] = creds_to_dict(creds)
    return build("gmail", "v1", credentials=creds)

def creds_to_dict(creds):
    return {
        "token":         creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri":     creds.token_uri,
        "client_id":     creds.client_id,
        "client_secret": creds.client_secret,
        "scopes":        creds.scopes
    }

def credentials_exist():
    return os.path.exists(CRED_PATH)

# ── Routes: Auth ───────────────────────────────────────────────────────────

@app.route("/")
def index():
    if "credentials" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html", creds_exist=credentials_exist())

@app.route("/login")
def login():
    if not credentials_exist():
        return render_template("login.html",
            error="credentials.json not found. Please follow setup instructions.",
            creds_exist=False)
    flow = Flow.from_client_secrets_file(CRED_PATH, scopes=SCOPES)
    flow.redirect_uri = url_for("oauth2callback", _external=True)
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )
    session["state"] = state
    return redirect(auth_url)

@app.route("/oauth2callback")
def oauth2callback():
    if not credentials_exist():
        return redirect(url_for("index"))
    flow = Flow.from_client_secrets_file(
        CRED_PATH, scopes=SCOPES, state=session.get("state")
    )
    flow.redirect_uri = url_for("oauth2callback", _external=True)
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials
    session["credentials"] = creds_to_dict(creds)

    # Get user info
    service = build("oauth2", "v2", credentials=creds)
    user_info = service.userinfo().get().execute()
    session["user"] = {
        "name":    user_info.get("name", "User"),
        "email":   user_info.get("email", ""),
        "picture": user_info.get("picture", "")
    }
    return redirect(url_for("dashboard"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/dashboard")
def dashboard():
    if "credentials" not in session:
        return redirect(url_for("index"))
    return render_template("index.html", user=session.get("user", {}))

# ── Routes: Gmail API ──────────────────────────────────────────────────────

@app.route("/api/emails")
def get_emails():
    if "credentials" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    service   = get_gmail_service()
    folder    = request.args.get("folder", "inbox")
    max_count = int(request.args.get("max", 30))

    # Map folder to Gmail query
    queries = {
        "inbox": "in:inbox -in:spam -in:trash",
        "spam":  "in:spam",
        "trash": "in:trash",
        "sent":  "in:sent",
    }
    query = queries.get(folder, "in:inbox")

    try:
        result   = service.users().messages().list(
            userId="me", q=query, maxResults=max_count
        ).execute()
        messages = result.get("messages", [])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    emails = []
    spam_count = 0
    ham_count  = 0

    for msg_ref in messages:
        try:
            msg_data = service.users().messages().get(
                userId="me", id=msg_ref["id"], format="full"
            ).execute()

            headers = {h["name"]: h["value"] for h in msg_data["payload"].get("headers", [])}
            subject = decode_str(headers.get("Subject", "(No Subject)"))
            from_   = decode_str(headers.get("From", ""))
            date_   = headers.get("Date", "")[:25]

            # Decode body
            payload = msg_data["payload"]
            raw_body = ""
            if "parts" in payload:
                for part in payload["parts"]:
                    if part.get("mimeType") == "text/plain":
                        data = part.get("body", {}).get("data", "")
                        if data:
                            raw_body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")[:500]
                            break
            else:
                data = payload.get("body", {}).get("data", "")
                if data:
                    raw_body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")[:500]

            ml = classify(subject, raw_body)
            label_ids = msg_data.get("labelIds", [])

            email_obj = {
                "id":         msg_ref["id"],
                "subject":    subject,
                "from_addr":  from_,
                "date":       date_,
                "snippet":    msg_data.get("snippet", "")[:120],
                "ml_label":   ml["label"],
                "confidence": ml["confidence"],
                "is_spam":    ml["is_spam"],
                "unread":     "UNREAD" in label_ids,
                "labels":     label_ids,
            }
            emails.append(email_obj)

            if ml["is_spam"]: spam_count += 1
            else:             ham_count  += 1

        except Exception:
            continue

    return jsonify({
        "emails":      emails,
        "total":       len(emails),
        "spam_count":  spam_count,
        "ham_count":   ham_count,
        "folder":      folder,
        "user":        session.get("user", {})
    })


@app.route("/api/emails/<msg_id>/trash", methods=["POST"])
def trash_email(msg_id):
    if "credentials" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    service = get_gmail_service()
    try:
        service.users().messages().trash(userId="me", id=msg_id).execute()
        return jsonify({"message": "Moved to trash", "id": msg_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/emails/<msg_id>/restore", methods=["POST"])
def restore_email(msg_id):
    if "credentials" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    service = get_gmail_service()
    try:
        service.users().messages().untrash(userId="me", id=msg_id).execute()
        return jsonify({"message": "Restored to inbox", "id": msg_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/spam/delete-all", methods=["POST"])
def delete_all_spam():
    """Fetch inbox, find ML-detected spam, move all to trash."""
    if "credentials" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    service = get_gmail_service()
    try:
        result   = service.users().messages().list(
            userId="me", q="in:inbox", maxResults=50
        ).execute()
        messages = result.get("messages", [])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    trashed = 0
    for msg_ref in messages:
        try:
            msg_data = service.users().messages().get(
                userId="me", id=msg_ref["id"], format="metadata",
                metadataHeaders=["Subject"]
            ).execute()
            headers = {h["name"]: h["value"] for h in msg_data["payload"].get("headers", [])}
            subject = decode_str(headers.get("Subject", ""))
            snippet = msg_data.get("snippet", "")
            ml = classify(subject, snippet)
            if ml["confidence"] >= AUTO_TRASH_THRESHOLD:
                service.users().messages().trash(userId="me", id=msg_ref["id"]).execute()
                trashed += 1
        except:
            continue

    return jsonify({"message": f"Moved {trashed} spam emails to trash", "count": trashed})


@app.route("/api/classify", methods=["POST"])
def classify_text():
    data    = request.get_json()
    subject = data.get("subject", "")
    body    = data.get("body", "")
    return jsonify(classify(subject, body))


@app.route("/api/stats")
def stats():
    s = dict(model_stats)
    s["model_loaded"] = pipeline is not None
    return jsonify(s)


@app.route("/api/user")
def user_info():
    if "credentials" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    return jsonify(session.get("user", {}))


if __name__ == "__main__":
    print("\n" + "="*55)
    print("  Smart Email Pro — Gmail Spam Detector")
    print("="*55)
    if not credentials_exist():
        print("  [!] credentials.json missing!")
        print("  [→] Follow README Step 1 to set up Google Cloud")
    if pipeline is None:
        print("  [!] ML model missing — run: python ml_model/train_model.py")
    else:
        print("  [OK] ML model loaded")
    print("  [→] Open: http://127.0.0.1:5000")
    print("="*55 + "\n")
port = int(os.environ.get("PORT", 5000))
app.run(debug=False, host="0.0.0.0", port=port)
