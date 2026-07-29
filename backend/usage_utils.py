from datetime import datetime, timezone
from typing import Any

from auth_utils import get_firestore_client

# Map actions to stat increments
ACTION_TO_STAT = {
    "upload_pdf": ("documents_uploaded", 1, "storage_used_bytes"),
    "ask_pdf": ("questions_asked", 1, None),
    "ask_rag": ("questions_asked", 1, None),
    "ai_generate_viva": ("ai_responses", 1, None),
    "ai_generate_exam": ("ai_responses", 1, None),
    "create_conversation": ("conversations_created", 1, None),
    "ai_response": ("ai_responses", 1, None),
}

# Storage estimate per action (bytes)
STORAGE_ESTIMATES = {
    "upload_pdf": 50 * 1024,  # ~50KB per document average
}


def get_user_stats_ref(db, uid):
    """Get or create user stats document."""
    stats_ref = db.collection("user_stats").document(uid)
    return stats_ref


def log_usage(
    user: dict,
    action: str,
    details: dict[str, Any] | None = None
):
    """
    Save a user activity log to Firebase Firestore.
    Also updates user statistics automatically.
    """

    try:
        db = get_firestore_client()
        uid = user.get("uid")

        log_data = {
            "uid": uid,
            "email": user.get("email"),
            "name": user.get("name"),
            "picture": user.get("picture"),
            "action": action,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc),
        }

        db.collection("usage_logs").add(log_data)

        # Auto-update stats based on action
        if action in ACTION_TO_STAT:
            stat_name, stat_value, storage_stat = ACTION_TO_STAT[action]

            stats_ref = get_user_stats_ref(db, uid)
            stats_doc = stats_ref.get()

            # Get current stats or defaults
            if stats_doc.exists:
                current_stats = stats_doc.to_dict()
            else:
                current_stats = {
                    "documents_uploaded": 0,
                    "conversations_created": 0,
                    "questions_asked": 0,
                    "ai_responses": 0,
                    "storage_used_bytes": 0,
                    "last_upload_date": None,
                    "created_at": datetime.now(timezone.utc),
                }

            # Build update
            updates = {
                stat_name: current_stats.get(stat_name, 0) + stat_value,
                "updated_at": datetime.now(timezone.utc),
            }

            # Add storage if applicable
            if storage_stat and action in STORAGE_ESTIMATES:
                storage_bytes = STORAGE_ESTIMATES[action]
                current_storage = current_stats.get(storage_stat, 0)
                updates[storage_stat] = current_storage + storage_bytes

            # Set last upload date for document uploads
            if stat_name == "documents_uploaded":
                updates["last_upload_date"] = datetime.now(timezone.utc)

            if stats_doc.exists:
                stats_ref.update(updates)
            else:
                current_stats.update(updates)
                stats_ref.set(current_stats)

    except Exception as error:
        # Do not break the app if logging fails.
        print(f"Usage logging failed: {error}")