"""
app.py — Smart Email Pro (Production-Ready for Render)
"""

import os, pickle, json
from flask import Flask, redirect, request, session, jsonify, render_template, url_for
from flask_cors import CORS
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import google.auth.transport.requests
import base64
from email.header import decode_header

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
ML_DIR      = os.path.join(BASE_DIR, "..", "ml_model")
MODEL_PATH  = os.path.join(ML_DIR, "spam_model.pkl")
STATS_PATH  = os.path.join(ML_DIR, "model_stats.pkl")
TMPL_DIR    = os.path.join(BASE_DIR, "..", "frontend", "templates")
STATIC_DIR  = os.path.join(BASE_DIR, "..", "frontend", "static")
CRED_PATH   = os.path.join(BASE_DIR, "..", "credentials.json")

app = Flask(__name__, template_folder=TMPL_DIR, static_folder=STATIC_DIR)
app.secret_key = os.environ.get("SECRET_KEY", "fallback-secret-smartemailpro-2026")
CORS(app)

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

def setup_credentials():
    creds_env = os.environ.get("GOOGLE_CREDENTIALS")
    if creds_env and not os.path.exists(CRED_PATH):
        try:
            json.loads(creds_env)
            with open(CRED_PATH, "w") as f:
                f.write(creds_env)
            print("[OK] credentials.json written from env variable.")
        except Exception as e:
            print(f"[ERROR] Could not write credentials.json: {e}")
    elif os.path.exists(CRED_PATH):
        print("[OK] credentials.json found on disk.")
    else:
        print("[WARN] No credentials found.")

setup_credentials()

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
        print("[WARN] spam_model.pkl not found.")

load_model()

def classify(subject, body):
    if pipeline is None:
        return {"label": "unknown", "confidence": 0.0, "is_spam": False}
    text  = (subject + " " + body).strip()
    proba = float(pipeline.predict_proba([text])[0][1])
    return {"label": "spam" if proba >= SPAM_THRESHOLD else "ham",
            "confidence": round(proba, 4), "is_spam": proba >= SPAM_THRESHOLD}

def decode_str(s):
    if not s: return ""
    parts = decode_header(s)
    result = ""
    for part, enc in parts:
        if isinstance(part, bytes):
            result += part.decode(enc or "utf-8", errors="replace")
        else:
            result += str(part)
    return result

def get_gmail_service():
    creds_data = session.get("credentials")
    if not creds_data: return None
    creds = Credentials(
        token=creds_data["token"],
        refresh_token=creds_data.get("refresh_token"),
        token_uri=creds_data["token_uri"],
        client_id=creds_data["client_id"],
        client_secret=creds_data["client_secret"],
        scopes=creds_data["scopes"]
    )
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(google.auth.transport.requests.Request())
            session["credentials"] = creds_to_dict(creds)
        except Exception as e:
            print(f"[WARN] Token refresh failed: {e}")
            return None
    return build("gmail", "v1", credentials=creds)

def creds_to_dict(creds):
    return {"token": creds.token, "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri, "client_id": creds.client_id,
            "client_secret": creds.client_secret, "scopes": creds.scopes}

def credentials_exist():
    return os.path.exists(CRED_PATH)

@app.route("/")
def index():
    if "credentials" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html", creds_exist=credentials_exist())

@app.route("/login")
def login():
    if not credentials_exist():
        return render_template("login.html",
            error="credentials.json not found. Set GOOGLE_CREDENTIALS env variable.",
            creds_exist=False)
    try:
        flow = Flow.from_client_secrets_file(CRED_PATH, scopes=SCOPES)
        flow.redirect_uri = url_for("oauth2callback", _external=True)
        auth_url, state = flow.authorization_url(
            access_type="offline", include_granted_scopes="true", prompt="consent")
        session["state"] = state
        return redirect(auth_url)
    except Exception as e:
        return render_template("login.html", error=f"Login error: {str(e)}", creds_exist=True)

@app.route("/oauth2callback")
def oauth2callback():
    if not credentials_exist():
        return redirect(url_for("index"))
    try:
        flow = Flow.from_client_secrets_file(
            CRED_PATH, scopes=SCOPES, state=session.get("state"))
        flow.redirect_uri = url_for("oauth2callback", _external=True)
        flow.fetch_token(authorization_response=request.url)
        creds = flow.credentials
        session["credentials"] = creds_to_dict(creds)
        service = build("oauth2", "v2", credentials=creds)
        user_info = service.userinfo().get().execute()
        session["user"] = {"name": user_info.get("name", "User"),
                           "email": user_info.get("email", ""),
                           "picture": user_info.get("picture", "")}
        return redirect(url_for("dashboard"))
    except Exception as e:
        return render_template("login.html", error=f"OAuth error: {str(e)}", creds_exist=True)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/dashboard")
def dashboard():
    if "credentials" not in session:
        return redirect(url_for("index"))
    return render_template("index.html", user=session.get("user", {}))

@app.route("/api/emails")
def get_emails():
    if "credentials" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    service = get_gmail_service()
    if not service:
        return jsonify({"error": "Gmail service unavailable. Please login again."}), 401
    folder    = request.args.get("folder", "inbox")
    max_count = int(request.args.get("max", 30))
    queries   = {"inbox": "in:inbox -in:spam -in:trash", "spam": "in:spam",
                 "trash": "in:trash", "sent": "in:sent"}
    query = queries.get(folder, "in:inbox")
    try:
        result   = service.users().messages().list(
            userId="me", q=query, maxResults=max_count).execute()
        messages = result.get("messages", [])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    emails = []
    spam_count = ham_count = 0
    for msg_ref in messages:
        try:
            msg_data  = service.users().messages().get(
                userId="me", id=msg_ref["id"], format="full").execute()
            headers   = {h["name"]: h["value"]
                         for h in msg_data["payload"].get("headers", [])}
            subject   = decode_str(headers.get("Subject", "(No Subject)"))
            from_     = decode_str(headers.get("From", ""))
            date_     = headers.get("Date", "")[:25]
            raw_body  = ""
            payload   = msg_data["payload"]
            if "parts" in payload:
                for part in payload["parts"]:
                    if part.get("mimeType") == "text/plain":
                        data = part.get("body", {}).get("data", "")
                        if data:
                            raw_body = base64.urlsafe_b64decode(data).decode(
                                "utf-8", errors="replace")[:500]
                            break
            else:
                data = payload.get("body", {}).get("data", "")
                if data:
                    raw_body = base64.urlsafe_b64decode(data).decode(
                        "utf-8", errors="replace")[:500]
            ml        = classify(subject, raw_body)
            label_ids = msg_data.get("labelIds", [])
            emails.append({"id": msg_ref["id"], "subject": subject,
                           "from_addr": from_, "date": date_,
                           "snippet": msg_data.get("snippet", "")[:120],
                           "ml_label": ml["label"], "confidence": ml["confidence"],
                           "is_spam": ml["is_spam"], "unread": "UNREAD" in label_ids,
                           "labels": label_ids})
            if ml["is_spam"]: spam_count += 1
            else:             ham_count  += 1
        except Exception:
            continue
    return jsonify({"emails": emails, "total": len(emails),
                    "spam_count": spam_count, "ham_count": ham_count,
                    "folder": folder, "user": session.get("user", {})})

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
    if "credentials" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    service = get_gmail_service()
    try:
        result   = service.users().messages().list(
            userId="me", q="in:inbox", maxResults=50).execute()
        messages = result.get("messages", [])
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    trashed = 0
    for msg_ref in messages:
        try:
            msg_data = service.users().messages().get(
                userId="me", id=msg_ref["id"], format="metadata",
                metadataHeaders=["Subject"]).execute()
            headers = {h["name"]: h["value"]
                       for h in msg_data["payload"].get("headers", [])}
            ml = classify(decode_str(headers.get("Subject", "")),
                          msg_data.get("snippet", ""))
            if ml["confidence"] >= AUTO_TRASH_THRESHOLD:
                service.users().messages().trash(
                    userId="me", id=msg_ref["id"]).execute()
                trashed += 1
        except Exception:
            continue
    return jsonify({"message": f"Moved {trashed} spam emails to trash", "count": trashed})

@app.route("/api/classify", methods=["POST"])
def classify_text():
    data = request.get_json()
    return jsonify(classify(data.get("subject", ""), data.get("body", "")))

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

@app.route("/health")
def health():
    return jsonify({"status": "ok", "model_loaded": pipeline is not None,
                    "creds_exist": credentials_exist()})

if __name__ == "__main__":
    port    = int(os.environ.get("PORT", 5000))
    is_prod = os.environ.get("FLASK_ENV") == "production"
    app.run(debug=not is_prod, host="0.0.0.0", port=port)
