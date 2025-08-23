from telethon import functions, types
from src.integrations.telegram import telegram_client
from src.database.mongo import db, get_user_data, update_user_data
from datetime import datetime
from src.telegram.keyboards import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import timedelta
import random
import logging

logger = logging.getLogger(__name__)

class GiveawayManager:
    async def create_premium_giveaway(self, user_id, boost_peer, users_count, months, 
                                    only_new_subscribers=False, countries_iso2=None,
                                    additional_peers=None, prize_description=None):
        """
        Create a Telegram Premium giveaway
        """
        try:
            if not telegram_client.client:
                await telegram_client.initialize()
            
            # Get giveaway options
            result = await telegram_client.client(
                functions.payments.GetPremiumGiftCodeOptionsRequest(
                    boost_peer=boost_peer
                )
            )
            
            # Find matching option
            selected_option = None
            for option in result:
                if option.users == users_count and option.months == months:
                    selected_option = option
                    break
            
            if not selected_option:
                return {'success': False, 'error': 'No matching giveaway option found'}
            
            # Create giveaway purpose
            purpose = types.InputStorePaymentPremiumGiveaway(
                only_new_subscribers=only_new_subscribers,
                winners_are_visible=True,  # Make winners visible
                boost_peer=boost_peer,
                additional_peers=additional_peers or [],
                countries_iso2=countries_iso2 or [],
                prize_description=prize_description,
                random_id=random.randint(0, 2**32),
                until_date=int((datetime.now() + timedelta(days=7)).timestamp()),
                currency=selected_option.currency,
                amount=selected_option.amount
            )
            
            # Create invoice
            invoice = types.InputInvoicePremiumGiftCode(
                purpose=purpose,
                option=selected_option
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
                'giveaway_option': selected_option
            }
            
        except Exception as e:
            logger.error(f"Error creating premium giveaway: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def create_stars_giveaway(self, user_id, stars_amount, winners_count, 
                                  boost_peer, per_user_stars):
        """
        Create a Stars giveaway
        """
        try:
            if not telegram_client.client:
                await telegram_client.initialize()
            
            # Get stars giveaway options
            result = await telegram_client.client(
                functions.payments.GetStarsGiveawayOptionsRequest()
            )
            
            # Find matching option
            selected_option = None
            for option in result:
                if option.stars == stars_amount:
                    selected_option = option
                    break
            
            if not selected_option:
                return {'success': False, 'error': 'No matching stars giveaway option found'}
            
            # Create stars giveaway purpose
            purpose = types.InputStorePaymentStarsGiveaway(
                stars=stars_amount,
                boost_peer=boost_peer,
                users=winners_count,
                random_id=random.randint(0, 2**32),
                until_date=int((datetime.now() + timedelta(days=7)).timestamp()),
                currency=selected_option.currency,
                amount=selected_option.amount
            )
            
            # Create invoice
            invoice = types.InputInvoiceStars(
                purpose=purpose
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
                'giveaway_option': selected_option
            }
            
        except Exception as e:
            logger.error(f"Error creating stars giveaway: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def get_giveaway_info(self, peer, msg_id):
        """
        Get information about a specific giveaway
        """
        try:
            if not telegram_client.client:
                await telegram_client.initialize()
            
            result = await telegram_client.client(
                functions.payments.GetGiveawayInfoRequest(
                    peer=peer,
                    msg_id=msg_id
                )
            )
            
            return {'success': True, 'info': result}
        except Exception as e:
            logger.error(f"Error getting giveaway info: {str(e)}")
            return {'success': False, 'error': str(e)}
        
        # Add these functions at the end of giveaways.py

    async def handle_giveaway_creation(update, context):
        """Handle giveaway creation callback"""
        try:
            query = update.callback_query
            await query.answer()
            await query.message.edit_text(
                "Choose giveaway type:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Premium Giveaway", callback_data="giveaway_premium")],
                    [InlineKeyboardButton("Stars Giveaway", callback_data="giveaway_stars")]
                ])
            )
        except Exception as e:
            logger.error(f"Error in handle_giveaway_creation: {str(e)}")

    async def handle_premium_giveaway(update, context):
        """Handle premium giveaway callback"""
        try:
            query = update.callback_query
            user_id = query.from_user.id
            
            # Get user's boost peer (simplified)
            boost_peer = await get_user_boost_peer(user_id)
            
            result = await giveaway_manager.create_premium_giveaway(
                user_id=user_id,
                boost_peer=boost_peer,
                users_count=3,
                months=1
            )
            
            if result['success']:
                await query.answer("Premium giveaway created!")
            else:
                await query.answer(f"Error: {result['error']}")
                
        except Exception as e:
            logger.error(f"Error in handle_premium_giveaway: {str(e)}")
            await query.answer("Error creating premium giveaway")

    async def handle_stars_giveaway(update, context):
        """Handle stars giveaway callback"""
        try:
            query = update.callback_query
            user_id = query.from_user.id
            
            # Get user's boost peer (simplified)
            boost_peer = await get_user_boost_peer(user_id)
            
            result = await giveaway_manager.create_stars_giveaway(
                user_id=user_id,
                stars_amount=100,
                winners_count=5,
                boost_peer=boost_peer,
                per_user_stars=20
            )
            
            if result['success']:
                await query.answer("Stars giveaway created!")
            else:
                await query.answer(f"Error: {result['error']}")
                
        except Exception as e:
            logger.error(f"Error in handle_stars_giveaway: {str(e)}")
            await query.answer("Error creating stars giveaway")

    # Helper function (you might need to implement this)
    async def get_user_boost_peer(user_id):
        """Get user's boost peer - simplified implementation"""
        # This should be implemented based on your application logic
        return types.InputPeerUser(user_id=user_id, access_hash=0)

giveaway_manager = GiveawayManager()