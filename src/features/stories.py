from telethon import functions, types
from src.integrations.telegram import telegram_client
import logging

logger = logging.getLogger(__name__)

class StoryManager:
    async def send_story(self, peer, media, caption=None, privacy_rules=None):
        """Send a story to specified peer"""
        try:
            result = await telegram_client.client(
                functions.stories.SendStoryRequest(
                    peer=peer,
                    media=media,
                    caption=caption,
                    privacy_rules=privacy_rules or []
                )
            )
            return {'success': True, 'result': result}
        except Exception as e:
            logger.error(f"Error sending story: {str(e)}")
            return {'success': False, 'error': str(e)}