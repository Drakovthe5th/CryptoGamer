from src.database.firebase import db
from datetime import datetime  # Add this
import time

def set_maintenance_mode(enabled: bool):
    """Enable/disable maintenance mode"""
    db.collection("system_settings").document("maintenance").set({
        "enabled": enabled,
        "timestamp": datetime.now()
    })

def is_maintenance_mode() -> bool:
    """Check if maintenance mode is enabled"""
    doc = db.collection("system_settings").document("maintenance").get()
    if doc.exists:
        return doc.to_dict().get("enabled", False)
    return False