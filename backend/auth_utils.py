import os

import firebase_admin
from firebase_admin import auth, credentials
from fastapi import Header, HTTPException


def initialize_firebase():
    if firebase_admin._apps:
        return

    service_account_path = os.getenv(
        "FIREBASE_SERVICE_ACCOUNT_PATH",
        "firebase-service-account.json"
    )

    if not os.path.exists(service_account_path):
        raise RuntimeError("Firebase service account file not found.")

    cred = credentials.Certificate(service_account_path)
    firebase_admin.initialize_app(cred)


def get_current_user(authorization: str = Header(None)):
    initialize_firebase()

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail={
                "status": "error",
                "message": "Authorization header is missing."
            }
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={
                "status": "error",
                "message": "Invalid authorization format."
            }
        )

    token = authorization.replace("Bearer ", "")

    try:
        decoded_token = auth.verify_id_token(token)
        return {
            "uid": decoded_token.get("uid"),
            "email": decoded_token.get("email"),
            "name": decoded_token.get("name"),
            "picture": decoded_token.get("picture")
        }

    except Exception:
        raise HTTPException(
            status_code=401,
            detail={
                "status": "error",
                "message": "Invalid or expired login token."
            }
        )