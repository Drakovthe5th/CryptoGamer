import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.database.mongo import get_user_data, update_user_data
from src.integrations.telegram import telegram_client
from datetime import datetime
from functools import functions, types

logger = logging.getLogger(__name__)

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