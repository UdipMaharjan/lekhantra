from datetime import datetime, timezone
from typing import Any

from auth_utils import get_firestore_client


def log_usage(
    user: dict,
    action: str,
    details: dict[str, Any] | None = None
):
    """
    Save a user activity log to Firebase Firestore.
    """

    try:
        db = get_firestore_client()

        log_data = {
            "uid": user.get("uid"),
            "email": user.get("email"),
            "name": user.get("name"),
            "picture": user.get("picture"),
            "action": action,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc),
        }

        db.collection("usage_logs").add(log_data)

    except Exception as error:
        # Do not break the app if logging fails.
        print(f"Usage logging failed: {error}")