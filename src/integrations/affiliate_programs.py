from telethon import functions, types
from src.integrations.telegram import telegram_client
from src.database.mongo import db
import logging

logger = logging.getLogger(__name__)

class AffiliateProgramManager:
    async def create_affiliate_program(self, bot_id, commission_permille, duration_months=None):
        """Create or update an affiliate program for a bot"""
        try:
            result = await telegram_client.client(
                functions.bots.UpdateStarRefProgramRequest(
                    bot=types.InputUser(user_id=bot_id, access_hash=0),
                    commission_permille=commission_permille,
                    duration_months=duration_months
                )
            )
            return {'success': True, 'program': result}
        except Exception as e:
            logger.error(f"Error creating affiliate program: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def get_suggested_programs(self, order_by_revenue=False, order_by_date=False, limit=20):
        """Get suggested affiliate programs"""
        try:
            result = await telegram_client.client(
                functions.payments.GetSuggestedStarRefBotsRequest(
                    order_by_revenue=order_by_revenue,
                    order_by_date=order_by_date,
                    limit=limit
                )
            )
            return {'success': True, 'programs': result}
        except Exception as e:
            logger.error(f"Error getting suggested programs: {str(e)}")
            return {'success': False, 'error': str(e)}