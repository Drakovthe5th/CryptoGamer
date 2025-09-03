from telethon import functions, types
from src.integrations.telegram import telegram_client
import logging

logger = logging.getLogger(__name__)

class AttachmentMenuManager:
    async def update_attachment_menu(self, bot_id, menu_items):
        """Update bot's attachment menu"""
        try:
            result = await telegram_client.client(
                functions.bots.UpdateAttachmentMenuRequest(
                    bot=types.InputUser(user_id=bot_id, access_hash=0),
                    menu_items=menu_items
                )
            )
            return {'success': True, 'result': result}
        except Exception as e:
            logger.error(f"Error updating attachment menu: {str(e)}")
            return {'success': False, 'error': str(e)}