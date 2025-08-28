import logging
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.database.mongo import get_user_data, update_user_data
from datetime import datetime
from src.integrations.telegram import telegram_client
from config import Config
from telethon import functions, types
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# Add the missing functions that miniapp.py expects
async def create_stars_invoice(user_id, product_id, title, description, price_stars, photo_url=None):
    """Create a Telegram Stars invoice for a product"""
    try:
        async with telegram_client:
            # Create invoice purpose
            purpose = types.InputStorePaymentStars(
                amount=price_stars,
                currency="XTR",
                description=description
            )
            
            # Create invoice
            invoice = types.InputInvoiceStars(
                purpose=purpose,
                title=title,
                description=description,
                photo=types.InputWebDocument(
                    url=photo_url or "https://example.com/default-product.png",
                    size=0,
                    mime_type="image/png",
                    attributes=[]
                ) if photo_url else None
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
                'title': title,
                'description': description,
                'price': price_stars,
                'currency': 'XTR'
            }
            
    except Exception as e:
        logger.error(f"Error creating Stars invoice: {str(e)}")
        return None

async def process_stars_payment(user_id, form_id, invoice_data):
    """Process a Telegram Stars payment"""
    try:
        async with telegram_client:
            # Send payment form
            result = await telegram_client(
                functions.payments.SendStarsFormRequest(
                    form_id=form_id,
                    invoice=types.InputInvoiceStars.from_dict(invoice_data)
                )
            )
            
            if hasattr(result, 'updates') and result.updates:
                # Payment successful
                return {
                    'success': True,
                    'stars_amount': invoice_data.get('amount', 0),
                    'transaction_id': f"stars_tx_{datetime.now().timestamp()}"
                }
            else:
                return {
                    'success': False,
                    'error': 'Payment failed'
                }
                
    except Exception as e:
        logger.error(f"Error processing Stars payment: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

async def get_stars_balance(user_id):
    """Get user's Telegram Stars balance"""
    try:
        async with telegram_client:
            status = await telegram_client(
                functions.payments.GetStarsStatusRequest(
                    peer=types.InputPeerSelf()
                )
            )
            
            return status.balance.stars if hasattr(status, 'balance') else 0
            
    except Exception as e:
        logger.error(f"Error getting Stars balance: {str(e)}")
        return 0

# Existing functions from the original file
async def handle_stars_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Telegram Stars purchase"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    
    # Get Stars topup options
    try:
        async with telegram_client:
            options = await telegram_client(
                functions.payments.GetStarsTopupOptionsRequest()
            )
            
        keyboard = []
        for option in options:
            keyboard.append([
                InlineKeyboardButton(
                    f"{option.stars} Stars - {option.amount/100} {option.currency}",
                    callback_data=f"stars_buy_{option.stars}"
                )
            ])
        
        await query.edit_message_text(
            "⭐ Telegram Stars Purchase\n\n"
            "Buy Stars to purchase premium items and subscriptions:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Error getting Stars options: {str(e)}")
        await query.edit_message_text("❌ Error loading Stars options")

async def process_stars_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process Stars purchase selection"""
    query = update.callback_query
    await query.answer()
    
    stars_amount = int(query.data.split('_')[-1])
    user_id = query.from_user.id
    
    # Get the specific topup option
    try:
        async with telegram_client:
            options = await telegram_client(
                functions.payments.GetStarsTopupOptionsRequest()
            )
            
        selected_option = next((opt for opt in options if opt.stars == stars_amount), None)
        if not selected_option:
            await query.edit_message_text("❌ Invalid Stars option")
            return
            
        # Create invoice for Stars purchase
        purpose = types.InputStorePaymentStarsTopup(
            stars=selected_option.stars,
            currency=selected_option.currency,
            amount=selected_option.amount
        )
        
        invoice = types.InputInvoiceStars(purpose=purpose)
        
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
        
        # Store form data for later processing
        context.user_data['stars_form'] = {
            'form_id': payment_form.form_id,
            'invoice': invoice,
            'stars': stars_amount
        }
        
        # Show payment instructions
        await query.edit_message_text(
            f"⭐ Purchase {stars_amount} Telegram Stars\n\n"
            f"Price: {selected_option.amount/100} {selected_option.currency}\n\n"
            "Complete your purchase through the Telegram payment interface.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Complete Purchase", callback_data="stars_complete_purchase")]
            ])
        )
        
    except Exception as e:
        logger.error(f"Error processing Stars purchase: {str(e)}")
        await query.edit_message_text("❌ Error processing Stars purchase")

async def complete_stars_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Complete Stars purchase and add Crew Credits to user account"""
    query = update.callback_query
    await query.answer()
    
    form_data = context.user_data.get('stars_form')
    if not form_data:
        await query.edit_message_text("❌ No purchase in progress")
        return
        
    try:
        async with telegram_client:
            result = await telegram_client(
                functions.payments.SendStarsFormRequest(
                    form_id=form_data['form_id'],
                    invoice=form_data['invoice']
                )
            )
            
        if hasattr(result, 'updates') and result.updates:
            # Update successful - add Crew Credits to user account
            user_id = query.from_user.id
            user_data = get_user_data(user_id)
            current_credits = user_data.get('crew_credits', 0)
            
            # Update user data with new Crew Credits
            update_user_data(user_id, {
                'crew_credits': current_credits + form_data['stars'] * 10,  # 10 credits per star
                'telegram_stars': user_data.get('telegram_stars', 0) + form_data['stars'],
                '$push': {
                    'stars_transactions': {
                        'type': 'purchase',
                        'stars': form_data['stars'],
                        'credits': form_data['stars'] * 10,
                        'date': datetime.now(),
                        'status': 'completed'
                    }
                }
            })
            
            await query.edit_message_text(
                f"✅ Successfully purchased {form_data['stars']} Telegram Stars!\n\n"
                f"Added {form_data['stars'] * 10} Crew Credits to your account.\n\n"
                "Use these credits to play Crypto Crew: Sabotage."
            )
            
        else:
            await query.edit_message_text("❌ Stars purchase failed")
            
    except Exception as e:
        logger.error(f"Error completing Stars purchase: {str(e)}")
        await query.edit_message_text("❌ Error completing Stars purchase")

async def handle_stars_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's Telegram Stars and Crew Credits balance"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    
    try:
        async with telegram_client:
            status = await telegram_client(
                functions.payments.GetStarsStatusRequest(
                    peer=types.InputPeerSelf()
                )
            )
            
        crew_credits = user_data.get('crew_credits', 0)
        game_coins = user_data.get('game_coins', 0)
        
        await query.edit_message_text(
            f"💰 Your Balances\n\n"
            f"• Telegram Stars: {status.balance.stars if hasattr(status, 'balance') else 0} Stars\n"
            f"• Crew Credits: {crew_credits} credits (for Crypto Crew only)\n"
            f"• Game Coins: {game_coins} GC (for all other games)\n\n"
            "Use Crew Credits to play Crypto Crew: Sabotage:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Buy Crew Credits", callback_data="buy_stars")],
                [InlineKeyboardButton("Play Crypto Crew", callback_data="play_sabotage")],
                [InlineKeyboardButton("Play Other Games", callback_data="games_list")]
            ])
        )
        
    except Exception as e:
        logger.error(f"Error getting balances: {str(e)}")
        await query.edit_message_text("❌ Error loading balances")

def validate_stars_purchase(user_id, stars_amount):
    """Validate if user can make this purchase"""
    if stars_amount <= 0:
        return False, "Invalid amount"
    if stars_amount > Config.MAX_STARS_PURCHASE:
        return False, f"Amount exceeds maximum of {Config.MAX_STARS_PURCHASE} Stars"
    return True, ""

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def create_stars_invoice(user_id, product_id, title, description, price_stars, photo_url=None):
    """Create a Telegram Stars invoice for a product with retry logic"""
    # Validate input
    is_valid, message = validate_stars_purchase(user_id, price_stars)
    if not is_valid:
        raise ValueError(message)
    
    try:
        async with telegram_client:
            # Create invoice purpose
            purpose = types.InputStorePaymentStars(
                amount=price_stars,
                currency="XTR",
                description=description
            )
            
            # Create invoice
            invoice = types.InputInvoiceStars(
                purpose=purpose,
                title=title,
                description=description,
                photo=types.InputWebDocument(
                    url=photo_url or "https://example.com/default-product.png",
                    size=0,
                    mime_type="image/png",
                    attributes=[]
                ) if photo_url else None
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
                'title': title,
                'description': description,
                'price': price_stars,
                'currency': 'XTR'
            }
            
    except Exception as e:
        logger.error(f"Error creating Stars invoice: {str(e)}")
        # Don't expose internal errors to users
        return None

# Add transaction tracking to database
async def record_stars_transaction(user_id, transaction_type, stars_amount, status, details=None):
    """Record Stars transaction in database"""
    transaction_data = {
        'user_id': user_id,
        'type': transaction_type,
        'stars_amount': stars_amount,
        'status': status,
        'timestamp': datetime.now(),
        'details': details or {}
    }
    
    # Add to user's transaction history
    update_user_data(user_id, {
        '$push': {
            'stars_transactions': transaction_data
        }
    })
    
    return transaction_data

# Add webhook handler for payment confirmations
async def handle_stars_webhook(payload):
    """Handle Stars payment webhook from Telegram"""
    try:
        # Verify webhook signature (implementation depends on Telegram's method)
        # if not verify_stars_webhook_signature(payload, request.headers.get('X-Telegram-Webhook-Signature')):
        #     return {"status": "error", "message": "Invalid signature"}
        
        # Process webhook based on event type
        event_type = payload.get('event_type')
        
        if event_type == 'payment.succeeded':
            user_id = payload.get('user_id')
            stars_amount = payload.get('stars_amount')
            transaction_id = payload.get('transaction_id')
            
            # Update user balance
            user_data = get_user_data(user_id)
            current_credits = user_data.get('crew_credits', 0)
            new_credits = current_credits + (stars_amount * Config.STARS_TO_CREDITS_RATE)
            
            update_user_data(user_id, {
                'crew_credits': new_credits,
                'telegram_stars': user_data.get('telegram_stars', 0) + stars_amount
            })
            
            # Record successful transaction
            await record_stars_transaction(
                user_id, 
                'purchase', 
                stars_amount, 
                'completed',
                {'transaction_id': transaction_id}
            )
            
            return {"status": "success"}
            
        elif event_type == 'payment.failed':
            user_id = payload.get('user_id')
            stars_amount = payload.get('stars_amount')
            
            # Record failed transaction
            await record_stars_transaction(
                user_id, 
                'purchase', 
                stars_amount, 
                'failed',
                {'reason': payload.get('failure_reason', 'unknown')}
            )
            
            return {"status": "success"}
            
        else:
            logger.warning(f"Unknown Stars webhook event type: {event_type}")
            return {"status": "ignored"}
            
    except Exception as e:
        logger.error(f"Error processing Stars webhook: {str(e)}")
        return {"status": "error", "message": str(e)}