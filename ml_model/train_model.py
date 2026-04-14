"""
train_model.py — Smart Email Pro
Train Naive Bayes + TF-IDF spam classifier.
Run this FIRST:  python ml_model/train_model.py
"""

import os, pickle
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_PATH  = os.path.join(BASE_DIR, "spam.csv")
MODEL_PATH = os.path.join(BASE_DIR, "spam_model.pkl")
STATS_PATH = os.path.join(BASE_DIR, "model_stats.pkl")

FALLBACK = [
    ("ham","Hi, are you free for a meeting tomorrow at 10am? Please confirm your availability."),
    ("ham","Your assignment submission deadline has been extended to next Friday."),
    ("ham","Please find attached the project report for your review and feedback."),
    ("ham","Dear team, the quarterly budget review is scheduled for Monday morning."),
    ("ham","Your OTP code is 847291. Valid for 5 minutes. Do not share this code."),
    ("ham","Authentication code 392018. Use this to complete your login process."),
    ("ham","Thanks for applying. We received your resume and will review it shortly."),
    ("ham","Can you review the pull request I submitted for the voice module?"),
    ("ham","Your order has been shipped. Tracking number TN2938475. Delivery in 2 days."),
    ("ham","Please reset your password using the link below. Valid for 1 hour only."),
    ("ham","Team lunch is scheduled for Friday at 1pm. Please confirm your attendance."),
    ("ham","Your interview is confirmed for April 15 at 10am. Best of luck!"),
    ("ham","Invoice attached for services rendered in March 2026. Due by end of month."),
    ("ham","Reminder: Your annual subscription renews in 7 days. No action needed."),
    ("ham","Just checking if you received my last email about the project update."),
    ("ham","The lecture notes for Chapter 5 have been uploaded to the student portal."),
    ("ham","Could you send me the updated version of the proposal document please?"),
    ("ham","Your package has been delivered. Please check your mailbox at your convenience."),
    ("ham","Happy birthday! Hope you have a wonderful day with family and friends."),
    ("ham","Server maintenance is scheduled for Sunday 2am to 4am. Plan accordingly."),
    ("spam","CONGRATULATIONS! You have been SELECTED as the lucky winner of $50000 cash prize! Click here NOW!"),
    ("spam","FREE money waiting for you! Claim your prize immediately before it expires today!"),
    ("spam","Earn $5000 per week from home! No experience needed! Guaranteed income! Act now!"),
    ("spam","URGENT: Your account has been suspended. Verify immediately or lose access permanently!"),
    ("spam","Buy cheap Viagra online! Best price guaranteed! Discreet shipping. Order now!"),
    ("spam","You won a FREE iPhone! Limited offer! Act now before deal expires! Click here!"),
    ("spam","Lose 30 pounds in 30 days! Miracle diet pill! Secret formula! Buy now cheap!"),
    ("spam","Hot singles in your area want to meet you! Click here for free adult dating!"),
    ("spam","URGENT loan offer! Get $10000 cash today! No credit check! Apply now instantly!"),
    ("spam","Double your Bitcoin investment! 100% guaranteed profit! Secret investment system!"),
    ("spam","Congratulations! Your email won the UK lottery! Claim $1 million prize now!"),
    ("spam","Work from home and earn $3000 daily! Exclusive opportunity! Limited spots available!"),
    ("spam","Your PayPal account is suspended! Verify now to avoid permanent ban! Urgent action!"),
    ("spam","Amazing weight loss secret doctors hate! Buy miracle pills now at lowest price!"),
    ("spam","FREE casino chips! Win big money online! No deposit needed! Play and win now!"),
    ("spam","WINNER! You have been specially selected! Call now to claim your free gift today!"),
    ("spam","Make money fast! Proven system! Join thousands already earning $5000 every week!"),
    ("spam","Exclusive offer for you only! Limited time discount! Buy now save 90 percent!"),
    ("spam","Your computer has a virus! Download our FREE software to remove it immediately!"),
    ("spam","Get rich quick! Invest in our guaranteed scheme! No risk! Maximum reward guaranteed!"),
]

def train():
    print("="*55)
    print("  Smart Email Pro — Spam Classifier Trainer")
    print("="*55)
    if os.path.exists(DATA_PATH):
        try:
            df = pd.read_csv(DATA_PATH, encoding="latin-1")[["v1","v2"]]
            df.columns = ["label","text"]
            print(f"[INFO] Loaded {len(df)} records from spam.csv")
        except:
            df = pd.DataFrame(FALLBACK, columns=["label","text"])
            print("[INFO] Using fallback dataset (40 records)")
    else:
        df = pd.DataFrame(FALLBACK, columns=["label","text"])
        print("[INFO] spam.csv not found — using fallback dataset (40 records)")

    df = df.dropna()
    df["label_num"] = (df["label"].str.strip().str.lower() == "spam").astype(int)
    print(f"[INFO] Ham: {(df['label_num']==0).sum()}  Spam: {(df['label_num']==1).sum()}")

    X_train, X_test, y_train, y_test = train_test_split(
        df["text"].values, df["label_num"].values,
        test_size=0.2, random_state=42, stratify=df["label_num"].values
    )

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(stop_words="english", ngram_range=(1,2), max_features=10000, sublinear_tf=True)),
        ("clf",   MultinomialNB(alpha=0.1))
    ])
    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)

    stats = {
        "accuracy":   round(accuracy_score(y_test, y_pred)*100, 2),
        "precision":  round(precision_score(y_test, y_pred, zero_division=0)*100, 2),
        "recall":     round(recall_score(y_test, y_pred, zero_division=0)*100, 2),
        "f1":         round(f1_score(y_test, y_pred, zero_division=0)*100, 2),
        "train_size": len(X_train),
        "test_size":  len(X_test),
        "total":      len(df),
    }
    print(f"\n  Accuracy : {stats['accuracy']}%")
    print(f"  Precision: {stats['precision']}%")
    print(f"  Recall   : {stats['recall']}%")
    print(f"  F1 Score : {stats['f1']}%")

    with open(MODEL_PATH,"wb") as f: pickle.dump(pipeline, f)
    with open(STATS_PATH,"wb") as f: pickle.dump(stats, f)
    print(f"\n[OK] Model saved → {MODEL_PATH}")
    print("="*55)
    print("  Done! Now run:  python backend/app.py")
    print("="*55)

if __name__ == "__main__":
    train()
