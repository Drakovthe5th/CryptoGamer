from src.telegram.auth import validate_telegram_data, get_authenticated_user_id
from src.telegram.config_manager import config_manager

def get_stars_module():
    """Lazy import for stars module to avoid circular imports"""
    from src.telegram.stars import (
        create_stars_invoice, process_stars_payment, get_stars_balance,
        handle_stars_webhook, record_stars_transaction
    )
    return {
        'create_stars_invoice': create_stars_invoice,
        'process_stars_payment': process_stars_payment,
        'get_stars_balance': get_stars_balance,
        'handle_stars_webhook': handle_stars_webhook,
        'record_stars_transaction': record_stars_transaction
    }

def get_web_events_module():
    """Lazy import for web events module"""
    from src.telegram.web_events import handle_web_event
    return {'handle_web_event': handle_web_event}

def get_attachment_menu_module():
    """Lazy import for attachment menu module"""
    from src.telegram.attachment_menu import AttachmentMenuManager
    return {'AttachmentMenuManager': AttachmentMenuManager}

# Export the lazy import functions
__all__ = [
    'validate_telegram_data',
    'get_authenticated_user_id',
    'config_manager',
    'get_stars_module',
    'get_web_events_module',
    'get_attachment_menu_module'
]