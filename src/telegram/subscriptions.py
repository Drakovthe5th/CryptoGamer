import logging
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.database.mongo import get_user_data, update_user_data
from src.integrations.telegram import telegram_client
from datetime import datetime
from telethon import functions, types

logger = logging.getLogger(__name__)

# Add the missing functions that miniapp.py expects
async def create_subscription_invoice(user_id, channel_id, period, amount):
    """Create a subscription invoice for a channel"""
    try:
        async with telegram_client:
            # Get channel info
            channel = await telegram_client.get_entity(channel_id)
            
            # Create subscription purpose
            purpose = types.InputStorePaymentPremiumSubscription(
                user_id=user_id,
                amount=amount,
                currency="XTR",
                period=period
            )
            
            # Create invoice
            invoice = types.InputInvoiceStars(
                purpose=purpose,
                title=f"Subscription to {channel.title}",
                description=f"{period}-day subscription to {channel.title}",
                photo=types.InputWebDocument(
                    url=getattr(channel, 'photo', None) or "https://example.com/default-channel.png",
                    size=0,
                    mime_type="image/png",
                    attributes=[]
                )
            )
            
            # Get payment form
            payment_form = await telegram_client(
                functions.payments.GetPaymentFormRequest(
                    invoice=invoice,
                    theme_params=types.DataJSON(
                        data=json.dumps({
                            "bg_color": "#000000",
                            "text_color": "#ffffff",
                            "hint_color": "#aaaaaa",
                            "link_color": "#ffcc00",
                            "button_color": "#ffcc00",
                            "button_text_color": "#000000"
                        })
                    )
                )
            )
            
            return {
                'form_id': payment_form.form_id,
                'invoice': invoice.to_dict(),
                'url': f"https://t.me/invoice/{payment_form.form_id}",
                'title': f"Subscription to {channel.title}",
                'description': f"{period}-day subscription",
                'price': amount,
                'currency': 'XTR',
                'period': period
            }
            
    except Exception as e:
        logger.error(f"Error creating subscription invoice: {str(e)}")
        return None

async def get_user_subscriptions(user_id):
    """Get user's active subscriptions"""
    try:
        async with telegram_client:
            # Get user's subscriptions from Telegram
            result = await telegram_client(
                functions.payments.GetUserSubscriptionsRequest()
            )
            
            subscriptions = []
            for sub in result.subscriptions:
                subscriptions.append({
                    'id': sub.id,
                    'channel_id': sub.channel_id,
                    'start_date': sub.start_date,
                    'expire_date': sub.expire_date,
                    'amount': sub.amount,
                    'currency': sub.currency
                })
            
            return subscriptions
            
    except Exception as e:
        logger.error(f"Error getting user subscriptions: {str(e)}")
        return []

async def cancel_subscription(user_id, subscription_id):
    """Cancel a subscription"""
    try:
        async with telegram_client:
            result = await telegram_client(
                functions.payments.CancelSubscriptionRequest(
                    subscription_id=subscription_id
                )
            )
            
            if result:
                # Update user data
                update_user_data(user_id, {
                    '$pull': {
                        'subscriptions': {'id': subscription_id}
                    }
                })
                
                return True
            return False
            
    except Exception as e:
        logger.error(f"Error canceling subscription: {str(e)}")
        return False

# Keep the original function from the file
async def handle_stars_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's active Stars subscriptions"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    try:
        async with telegram_client:
            status = await telegram_client(
                functions.payments.GetStarsSubscriptionsRequest(
                    peer=types.InputPeerSelf()
                )
            )
            
        if not status.subscriptions:
            await query.edit_message_text(
                "📋 You don't have any active subscriptions.\n\n"
                "Subscribe to premium channels or bot services using Telegram Stars.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Browse Subscriptions", callback_data="browse_subscriptions")],
                    [InlineKeyboardButton("Back", callback_data="premium_main")]
                ])
            )
            return
            
        text = "⭐ Your Active Subscriptions\n\n"
        keyboard = []
        
        for sub in status.subscriptions:
            # Format subscription info
            until_date = datetime.fromtimestamp(sub.until_date)
            text += f"• {sub.title}\n"
            text += f"  Renews: {until_date.strftime('%Y-%m-%d')}\n"
            text += f"  Cost: {sub.pricing.amount} Stars/{sub.pricing.period//86400} days\n\n"
            
            keyboard.append([
                InlineKeyboardButton(
                    f"Manage {sub.title}", 
                    callback_data=f"manage_sub_{sub.id}"
                )
            ])
            
        keyboard.append([InlineKeyboardButton("Back", callback_data="premium_main")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Error getting subscriptions: {str(e)}")
        await query.edit_message_text("❌ Error loading subscriptions")