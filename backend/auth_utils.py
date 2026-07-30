import os
from pathlib import Path

from fastapi import Header, HTTPException


def _firebase_modules():
    """Import Firebase Admin only for authenticated or Firestore-backed calls."""
    import firebase_admin
    from firebase_admin import auth, credentials, firestore

    return firebase_admin, auth, credentials, firestore


def initialize_firebase():
    firebase_admin, _, credentials, _ = _firebase_modules()
    if firebase_admin._apps:
        return

    service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")

    if service_account_json:
        import json
        service_account_info = json.loads(service_account_json)
        cred = credentials.Certificate(service_account_info)
        firebase_admin.initialize_app(cred)
        return

    service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
    if not service_account_path:
        service_account_path = str(Path(__file__).resolve().with_name("firebase-service-account.json"))

    if not os.path.exists(service_account_path):
        raise RuntimeError("Firebase service account file not found.")

    cred = credentials.Certificate(service_account_path)
    firebase_admin.initialize_app(cred)

def get_current_user(authorization: str = Header(None)):
    print(f"[AUTH] get_current_user called")
    print(f"[AUTH] authorization header present: {bool(authorization)}")

    if not authorization:
        print("[AUTH] No authorization header!")
        raise HTTPException(
            status_code=401,
            detail={
                "status": "error",
                "message": "Authorization header is missing."
            }
        )

    if not authorization.startswith("Bearer "):
        print("[AUTH] Invalid authorization format!")
        raise HTTPException(
            status_code=401,
            detail={
                "status": "error",
                "message": "Invalid authorization format."
            }
        )

    token = authorization.replace("Bearer ", "")

    try:
        initialize_firebase()
        _, auth, _, _ = _firebase_modules()
        decoded_token = auth.verify_id_token(token)
        print(f"[AUTH] Token verified successfully")
        print(f"[AUTH] Decoded token UID: {decoded_token.get('uid')}")
        return {
            "uid": decoded_token.get("uid"),
            "email": decoded_token.get("email"),
            "name": decoded_token.get("name"),
            "picture": decoded_token.get("picture")
        }

    except Exception as e:
        print(f"[AUTH] Token verification failed: {e}")
        raise HTTPException(
            status_code=401,
            detail={
                "status": "error",
                "message": "Invalid or expired login token."
            }
        )
    
def get_firestore_client():
    initialize_firebase()
    _, _, _, firestore = _firebase_modules()
    return firestore.client()
