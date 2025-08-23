from telethon import functions, types
from src.integrations.telegram import telegram_client
from src.database.mongo import db
import logging

logger = logging.getLogger(__name__)

class GiftManager:
    async def get_available_gifts(self, hash=0):
        """
        Get available star gifts
        """
        try:
            if not telegram_client.client:
                await telegram_client.initialize()
            
            result = await telegram_client.client(
                functions.payments.GetStarGiftsRequest(hash=hash)
            )
            
            return {'success': True, 'gifts': result}
        except Exception as e:
            logger.error(f"Error getting available gifts: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def send_star_gift(self, user_id, recipient_id, gift_id, 
                           hide_name=False, message=None):
        """
        Send a star gift to another user
        """
        try:
            if not telegram_client.client:
                await telegram_client.initialize()
            
            # Create invoice
            invoice = types.InputInvoiceStarGift(
                hide_name=hide_name,
                user_id=await self._get_input_user(recipient_id),
                gift_id=gift_id,
                message=message
            )
            
            # Get payment form
            payment_form = await telegram_client.client(
                functions.payments.GetPaymentFormRequest(
                    invoice=invoice
                )
            )
            
            return {
                'success': True,
                'payment_form': payment_form,
                'gift_id': gift_id
            }
            
        except Exception as e:
            logger.error(f"Error sending star gift: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def get_user_gifts(self, user_id, offset='', limit=50):
        """
        Get gifts received by a user
        """
        try:
            if not telegram_client.client:
                await telegram_client.initialize()
            
            result = await telegram_client.client(
                functions.payments.GetUserStarGiftsRequest(
                    user_id=await self._get_input_user(user_id),
                    offset=offset,
                    limit=limit
                )
            )
            
            return {'success': True, 'gifts': result}
        except Exception as e:
            logger.error(f"Error getting user gifts: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def save_gift(self, user_id, sender_id, msg_id, unsave=False):
        """
        Save or unsave a received gift
        """
        try:
            if not telegram_client.client:
                await telegram_client.initialize()
            
            result = await telegram_client.client(
                functions.payments.SaveStarGiftRequest(
                    unsave=unsave,
                    user_id=await self._get_input_user(sender_id),
                    msg_id=msg_id
                )
            )
            
            return {'success': True, 'result': result}
        except Exception as e:
            logger.error(f"Error saving gift: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def convert_gift_to_stars(self, user_id, sender_id, msg_id):
        """
        Convert a gift to stars
        """
        try:
            if not telegram_client.client:
                await telegram_client.initialize()
            
            result = await telegram_client.client(
                functions.payments.ConvertStarGiftRequest(
                    user_id=await self._get_input_user(sender_id),
                    msg_id=msg_id
                )
            )
            
            return {'success': True, 'result': result}
        except Exception as e:
            logger.error(f"Error converting gift to stars: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def _get_input_user(self, user_id):
        """Convert user ID to InputUser"""
        user = await telegram_client.client.get_entity(user_id)
        return types.InputUser(user_id=user.id, access_hash=user.access_hash)
    
    # Add these functions at the end of gifts.py

async def handle_gift_sending(update, context):
    """Handle gift sending callback"""
    try:
        query = update.callback_query
        data = query.data.split(':')
        gift_id = data[1]
        recipient_id = data[2]
        
        result = await gift_manager.send_star_gift(
            user_id=query.from_user.id,
            recipient_id=recipient_id,
            gift_id=gift_id
        )
        
        if result['success']:
            await query.answer("Gift sent successfully!")
        else:
            await query.answer(f"Error: {result['error']}")
            
    except Exception as e:
        logger.error(f"Error in handle_gift_sending: {str(e)}")
        await query.answer("Error sending gift")

async def handle_gift_view(update, context):
    """Handle gift view callback"""
    try:
        query = update.callback_query
        user_id = query.data.split(':')[1]
        
        result = await gift_manager.get_user_gifts(user_id)
        
        if result['success']:
            # Format and display gifts
            gifts_text = "\n".join([f"🎁 {gift.title}" for gift in result['gifts']])
            await query.message.edit_text(f"Your gifts:\n{gifts_text}")
        else:
            await query.answer(f"Error: {result['error']}")
            
    except Exception as e:
        logger.error(f"Error in handle_gift_view: {str(e)}")
        await query.answer("Error viewing gifts")

async def handle_gift_save(update, context):
    """Handle gift save/unsave callback"""
    try:
        query = update.callback_query
        data = query.data.split(':')
        msg_id = data[1]
        sender_id = data[2]
        unsave = 'unsave' in query.data
        
        result = await gift_manager.save_gift(
            user_id=query.from_user.id,
            sender_id=sender_id,
            msg_id=msg_id,
            unsave=unsave
        )
        
        action = "unsaved" if unsave else "saved"
        if result['success']:
            await query.answer(f"Gift {action}!")
        else:
            await query.answer(f"Error: {result['error']}")
            
    except Exception as e:
        logger.error(f"Error in handle_gift_save: {str(e)}")
        await query.answer("Error saving gift")

async def handle_gift_convert(update, context):
    """Handle gift to stars conversion callback"""
    try:
        query = update.callback_query
        data = query.data.split(':')
        msg_id = data[1]
        sender_id = data[2]
        
        result = await gift_manager.convert_gift_to_stars(
            user_id=query.from_user.id,
            sender_id=sender_id,
            msg_id=msg_id
        )
        
        if result['success']:
            await query.answer("Gift converted to stars!")
        else:
            await query.answer(f"Error: {result['error']}")
            
    except Exception as e:
        logger.error(f"Error in handle_gift_convert: {str(e)}")
        await query.answer("Error converting gift")

gift_manager = GiftManager()