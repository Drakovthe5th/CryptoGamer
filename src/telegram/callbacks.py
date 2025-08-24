import os
from bson import ObjectId
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.database.mongo import (
    get_user_data, update_balance, update_leaderboard_points, 
    get_db, SERVER_TIMESTAMP
)
from src.features.otc_desk import otc_desk
from src.features.quests import complete_quest
from src.integrations.ton import process_ton_withdrawal
from src.utils.conversions import game_coins_to_ton, convert_currency, calculate_fee
from src.utils.validators import validate_ton_address, validate_mpesa_number, validate_email
from src.telegram.config_manager import config_manager
from src.integrations.telegram import telegram_client
from config import Config
from src.telegram.stars import (
    handle_stars_purchase, 
    process_stars_purchase, 
    complete_stars_purchase,
    handle_stars_balance,
    handle_giveaway_creation,
    handle_premium_giveaway,
    handle_stars_giveaway,
    handle_gift_sending,
    handle_gift_view,
    handle_gift_save,
    handle_gift_convert
)
from src.telegram.subscriptions import handle_stars_subscriptions
from games.sabotage_game import SabotageGame
import random
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Add to callback query handler patterns
CALLBACK_HANDLERS = {
    "buy_stars": handle_stars_purchase,
    "stars_buy_.*": process_stars_purchase,
    "stars_complete_purchase": complete_stars_purchase,
    "stars_balance": handle_stars_balance,
    "stars_subscriptions": handle_stars_subscriptions,
    "giveaway_create": handle_giveaway_creation,
    "giveaway_premium": handle_premium_giveaway,
    "giveaway_stars": handle_stars_giveaway,
    "gift_send": handle_gift_sending,
    "gift_view": handle_gift_view,
    "gift_save": handle_gift_save,
    "gift_convert": handle_gift_convert
}

async def dismiss_suggestion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle suggestion dismissal"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('_')
    suggestion_type = data[1]
    user_id = query.from_user.id
    
    try:
        # Call Telegram API to dismiss suggestion
        async with telegram_client:
            result = await telegram_client(
                functions.help.DismissSuggestionRequest(
                    peer=types.InputPeerEmpty(),
                    suggestion=suggestion_type
                )
            )
            
        if result:
            await query.edit_message_text("✅ Suggestion dismissed")
        else:
            await query.edit_message_text("❌ Failed to dismiss suggestion")
            
    except Exception as e:
        logger.error(f"Error dismissing suggestion: {str(e)}")
        await query.edit_message_text("❌ Error dismissing suggestion")

async def show_suggestions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show pending suggestions to user"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    try:
        # Get client config
        client_config = await config_manager.get_client_config()
        pending_suggestions = client_config.get('pending_suggestions', [])
        
        if not pending_suggestions:
            await query.edit_message_text("No suggestions at this time!")
            return
            
        keyboard = []
        for suggestion in pending_suggestions:
            button_text = _get_suggestion_text(suggestion)
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"suggestion_{suggestion}")])
        
        await query.edit_message_text(
            "💡 Suggestions for you:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Error showing suggestions: {str(e)}")
        await query.edit_message_text("❌ Error loading suggestions")

def _get_suggestion_text(suggestion_type):
    """Get user-friendly text for suggestion type"""
    suggestion_texts = {
        "AUTOARCHIVE_POPULAR": "⚡ Enable Auto-Archive",
        "VALIDATE_PASSWORD": "🔒 Check Password",
        "VALIDATE_PHONE_NUMBER": "📱 Verify Phone",
        "NEWCOMER_TICKS": "💬 Message Status Guide",
        "SETUP_PASSWORD": "🛡️ Setup 2FA",
        "PREMIUM_ANNUAL": "⭐ Get Premium (Annual)",
        "PREMIUM_UPGRADE": "⚡ Upgrade to Annual",
        "PREMIUM_RESTORE": "🔄 Restore Premium",
        "PREMIUM_CHRISTMAS": "🎄 Gift Premium",
        "PREMIUM_GRACE": "⏳ Extend Premium",
        "BIRTHDAY_SETUP": "🎂 Set Birthday",
        "STARS_SUBSCRIPTION_LOW_BALANCE": "💫 Top Up Stars",
        "USERPIC_SETUP": "🖼️ Set Profile Picture"
    }
    return suggestion_texts.get(suggestion_type, suggestion_type)

async def set_ton_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt user to set TON address"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['awaiting_ton'] = True
    await query.edit_message_text(
        "🌐 Please send your TON address in the following format:\n"
        "`EQAhF...` (standard TON wallet address)\n\n"
        "Or type /cancel to abort",
        parse_mode='Markdown'
    )

async def set_mpesa_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt user to set M-Pesa number"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['awaiting_mpesa'] = True
    await query.edit_message_text(
        "📱 Please send your M-Pesa number in the following format:\n"
        "`254712345678` (12 digits starting with 254)\n\n"
        "Or type /cancel to abort",
        parse_mode='Markdown'
    )

async def set_paypal_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt user to set PayPal email"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['awaiting_paypal'] = True
    await query.edit_message_text(
        "💳 Please send your PayPal email address:\n"
        "`example@domain.com`\n\n"
        "Or type /cancel to abort",
        parse_mode='Markdown'
    )

# ================
# GAME HANDLERS
# ================

async def trivia_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a trivia game session"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    
    # Check game cooldown
    last_played = user_data.get('last_played', {}).get('trivia')
    if last_played and (datetime.datetime.now() - last_played).seconds < Config.GAME_COOLDOWN * 60:
        cooldown = Config.GAME_COOLDOWN * 60 - (datetime.datetime.now() - last_played).seconds
        await query.edit_message_text(
            f"⏳ You can play trivia again in {cooldown // 60} minutes!"
        )
        return
    
    # TON-themed questions
    questions = [
        {
            "question": "What blockchain does TON use?",
            "options": ["Proof of Work", "Proof of Stake", "Byzantine Fault Tolerance", "Sharded Proof of Stake"],
            "correct": 3
        },
        {
            "question": "What is the native cryptocurrency of TON?",
            "options": ["TON Coin", "Toncoin", "Gram", "Telegram Coin"],
            "correct": 1
        },
        {
            "question": "What does TON stand for?",
            "options": ["Telegram Open Network", "The Open Network", "Token Open Network", "Telegram Operating Network"],
            "correct": 1
        },
        {
            "question": "What unique feature does TON have?",
            "options": ["Instant Hypercube Routing", "Quantum Resistance", "Infinite Sharding", "Telegram Integration"],
            "correct": 2
        },
        {
            "question": "What is the transaction speed of TON?",
            "options": ["1,000 TPS", "10,000 TPS", "100,000 TPS", "1,000,000 TPS"],
            "correct": 3
        }
    ]
    
    # Select random question
    question = random.choice(questions)
    context.user_data['trivia_question'] = question
    context.user_data['trivia_answer'] = question['correct']
    
    # Build options keyboard
    keyboard = []
    for idx, option in enumerate(question['options']):
        keyboard.append([InlineKeyboardButton(option, callback_data=f"trivia_{idx}")])
    
    await query.edit_message_text(
        f"🧠 TRIVIA QUESTION:\n\n{question['question']}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_trivia_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process user's answer to trivia question"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    selected = int(query.data.split('_')[1])
    correct_idx = context.user_data.get('trivia_answer')
    question = context.user_data.get('trivia_question')
    
    # Get database instance
    db = get_db()
    
    # Update last played time - MongoDB syntax
    db.users.update_one(
        {"user_id": user_id},
        {"$set": {"last_played.trivia": SERVER_TIMESTAMP}}
    )
    
    if selected == correct_idx:
        # Correct answer
        reward = Config.REWARDS['trivia_correct']
        new_balance = update_balance(user_id, reward)
        update_leaderboard_points(user_id, 5)
        
        await query.edit_message_text(
            f"✅ Correct! You earned {reward:.6f} TON\n"
            f"💰 New balance: {game_coins_to_ton(new_balance):.6f} TON"
        )
    else:
        # Incorrect answer
        reward = Config.REWARDS.get('trivia_incorrect', 0.001)
        new_balance = update_balance(user_id, reward)
        
        correct_answer = question['options'][correct_idx]
        await query.edit_message_text(
            f"❌ Wrong! The correct answer was: {correct_answer}\n"
            f"💡 You still earned {reward:.6f} TON for playing!\n"
            f"💰 New balance: {game_coins_to_ton(new_balance):.6f} TON"
        )

async def spin_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start spin wheel game"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    
    # Check game cooldown
    last_played = user_data.get('last_played', {}).get('spin')
    if last_played and (datetime.datetime.now() - last_played).seconds < Config.GAME_COOLDOWN * 60:
        cooldown = Config.GAME_COOLDOWN * 60 - (datetime.datetime.now() - last_played).seconds
        await query.edit_message_text(
            f"⏳ You can spin again in {cooldown // 60} minutes!"
        )
        return
    
    keyboard = [[InlineKeyboardButton("🎰 SPIN THE WHEEL!", callback_data="spin_action")]]
    
    await query.edit_message_text(
        "🎰 SPIN THE WHEEL!\n\n"
        "Test your luck and win up to 0.1 TON!",
        reply_markup=InlineKeyboardMarkup(keyboard))

async def spin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process wheel spin"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Get database instance
    db = get_db()
    
    # Update last played time - MongoDB syntax
    db.users.update_one(
        {"user_id": user_id},
        {"$set": {"last_played.spin": SERVER_TIMESTAMP}}
    )
    
    # Determine win (40% chance)
    if random.random() < 0.4:
        reward = Config.REWARDS['spin_win']
        text = "🎉 JACKPOT! You won!"
    else:
        reward = Config.REWARDS['spin_loss']
        text = "😢 Better luck next time!"
    
    new_balance = update_balance(user_id, reward)
    
    await query.edit_message_text(
        f"{text}\n"
        f"💰 You earned: {reward:.6f} TON\n"
        f"💎 New balance: {game_coins_to_ton(new_balance):.6f} TON"
    )

# =====================
# WITHDRAWAL HANDLERS
# =====================

async def process_withdrawal_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process withdrawal method selection"""
    query = update.callback_query
    await query.answer()
    data = query.data.split('_')
    
    if data[1] == 'cancel':
        await query.edit_message_text("Withdrawal cancelled.")
        return
        
    method = data[1]
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    balance = user_data.get('balance', 0)
    
    MIN_WITHDRAWAL_GC = 200000  # 200,000 GC = 100 TON
    
    # Get game coins from user data
    game_coins = user_data.get('game_coins', 0)
    
    if game_coins < MIN_WITHDRAWAL_GC:
        await query.edit_message_text(
            f"❌ Minimum withdrawal: {MIN_WITHDRAWAL_GC:,} GC (100 TON)\n"
            f"Your balance: {game_coins:,} GC"
        )
        return
        
    # Process withdrawal based on method
    if method == 'ton':
        context.user_data['withdrawal_method'] = 'ton'
        context.user_data['withdrawal_amount_gc'] = MIN_WITHDRAWAL_GC
        await query.edit_message_text(
            "🌐 Please enter your TON wallet address:",
            parse_mode='Markdown'
        )
    else:
        # OTC desk cash withdrawal
        currencies = otc_desk.buy_rates.keys()
        keyboard = [[InlineKeyboardButton(currency, callback_data=f"cash_{currency}")] 
                    for currency in currencies]
        
        context.user_data['withdrawal_method'] = method
        context.user_data['withdrawal_amount'] = balance
        
        await query.edit_message_text(
            f"💱 Select currency for your {balance:.6f} TON:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def process_otc_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process currency selection for OTC withdrawal"""
    query = update.callback_query
    await query.answer()
    currency = query.data.split('_')[1]
    user_id = query.from_user.id
    
    method = context.user_data['withdrawal_method']
    amount = context.user_data['withdrawal_amount']
    
    user_data = get_user_data(user_id)
    payment_details = user_data.get('payment_methods', {}).get(method, {})
    
    rate = otc_desk.get_buy_rate(currency)
    if not rate:
        await query.edit_message_text("❌ Invalid currency selected")
        return
        
    fiat_amount = convert_currency(amount, rate)
    fee = calculate_fee(fiat_amount, Config.OTC_FEE_PERCENT, Config.MIN_OTC_FEE)
    total = fiat_amount - fee
    
    deal_data = {
        'user_id': user_id,
        'amount_ton': amount,
        'currency': currency,
        'payment_method': method,
        'rate': rate,
        'fiat_amount': fiat_amount,
        'fee': fee,
        'total': total,
        'status': 'pending',
        'created_at': SERVER_TIMESTAMP,
        'payment_details': payment_details
    }
    
    # Get database instance
    db = get_db()
    
    # MongoDB insert
    result = db.otc_deals.insert_one(deal_data)
    deal_id = result.inserted_id
    
    update_balance(user_id, -amount)
    
    payment_info = ""
    if method == 'M-Pesa':
        payment_info = f"📱 M-Pesa Number: {payment_details.get('phone', 'N/A')}"
    elif method == 'PayPal':
        payment_info = f"💳 PayPal Email: {payment_details.get('email', 'N/A')}"
    elif method == 'Bank Transfer':
        payment_info = f"🏦 Bank Account: {payment_details.get('account_number', 'N/A')}"
    
    await query.edit_message_text(
        f"💸 Cash withdrawal processing!\n\n"
        f"• Deal ID: <code>{deal_id}</code>\n"
        f"• Amount: {amount:.6f} TON → {currency}\n"
        f"• Rate: {rate:.2f} {currency}/TON\n"
        f"• Fee: {fee:.2f} {currency}\n"
        f"• You Receive: {total:.2f} {currency}\n\n"
        f"{payment_info}\n\n"
        f"Payment will be processed within 24 hours.",
        parse_mode='HTML'
    )

async def complete_ton_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Complete TON withdrawal with provided address"""
    user_id = update.effective_user.id
    address = update.message.text.strip()
    
    # Get withdrawal amount from context
    amount_gc = context.user_data.get('withdrawal_amount_gc', 0)
    ton_amount = game_coins_to_ton(amount_gc)
    
    if not validate_ton_address(address):
        await update.message.reply_text("❌ Invalid TON address format. Please try again.")
        return
    
    # Process TON withdrawal
    result = process_ton_withdrawal(user_id, ton_amount, address)
    
    if result and result.get('status') == 'success':
        withdrawal_data = {
            'user_id': user_id,
            'amount': ton_amount,
            'address': address,
            'tx_hash': result.get('tx_hash', ''),
            'status': 'pending',
            'created_at': SERVER_TIMESTAMP
        }
        
        # Get database instance
        db = get_db()
        
        # MongoDB insert
        db.withdrawals.insert_one(withdrawal_data)
        # Deduct game coins from user
        db.users.update_one(
            {"user_id": user_id},
            {"$inc": {"game_coins": -amount_gc}}
        )
        
        await update.message.reply_text(
            f"✅ Withdrawal of {ton_amount:.6f} TON is processing!\n"
            f"Transaction: https://tonscan.org/tx/{result.get('tx_hash', '')}"
        )
    else:
        error = result.get('error', 'Withdrawal failed') if result else 'Withdrawal failed'
        await update.message.reply_text(f"❌ Withdrawal failed: {error}")

# ================
# QUEST HANDLERS
# ================

async def quest_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show details of a specific quest"""
    query = update.callback_query
    await query.answer()
    quest_id = query.data.split('_')[1]
    
    # Get database instance
    db = get_db()
    
    # Get quest details with ObjectID conversion
    try:
        quest_doc = db.quests.find_one({"_id": ObjectId(quest_id)})
    except:
        quest_doc = None
        
    if not quest_doc:
        await query.edit_message_text("Quest not found.")
        return
    
    quest_data = quest_doc
    
    # Format quest details
    text = f"<b>{quest_data['title']}</b>\n\n"
    text += f"{quest_data['description']}\n\n"
    text += f"💎 Reward: {quest_data['reward_ton']:.6f} TON\n"
    text += f"⭐ Points: {quest_data['reward_points']}\n"
    
    # Check if user has completed quest
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    completed_quests = user_data.get('completed_quests', [])
    
    # Convert quest_id to string for comparison
    if str(quest_id) in completed_quests:
        text += "✅ You've already completed this quest!"
        keyboard = []
    else:
        text += "Tap below to complete this quest:"
        keyboard = [[InlineKeyboardButton("Complete Quest", callback_data=f"complete_{quest_id}")]]
    
    keyboard.append([InlineKeyboardButton("Back to Quests", callback_data="back_to_quests")])
    
    await query.edit_message_text(
        text, 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def complete_quest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mark a quest as completed for the user"""
    query = update.callback_query
    await query.answer()
    quest_id = query.data.split('_')[1]
    user_id = query.from_user.id
    
    # Call the complete_quest function
    if complete_quest(user_id, quest_id):
        await query.edit_message_text("✅ Quest completed! Rewards added to your account.")
    else:
        await query.edit_message_text("❌ Failed to complete quest. Please try again.")

# ===================
# PAYMENT METHOD HANDLERS
# ===================

async def select_payment_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment method selection for OTC"""
    query = update.callback_query
    await query.answer()
    method = query.data.split('_')[1]
    
    # Store selected method in context
    context.user_data['payment_method'] = method
    
    # Prompt for details based on method
    if method == 'M-Pesa':
        await query.edit_message_text(
            "📱 Please enter your M-Pesa number in the format:\n"
            "254712345678\n\n"
            "Or type /cancel to abort"
        )
    elif method == 'PayPal':
        await query.edit_message_text(
            "💳 Please enter your PayPal email address:\n"
            "example@domain.com\n\n"
            "Or type /cancel to abort"
        )
    elif method == 'Bank':
        await query.edit_message_text(
            "🏦 Please enter your bank details in the format:\n"
            "Bank Name, Account Name, Account Number\n\n"
            "Example: Equity Bank, John Doe, 123456789\n\n"
            "Or type /cancel to abort"
        )

async def save_payment_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save payment details to user profile"""
    user_id = update.effective_user.id
    method = context.user_data.get('payment_method')
    details = update.message.text.strip()
    
    if not method:
        await update.message.reply_text("❌ No payment method selected. Please start over.")
        return
    
    # Validate and save details
    if method == 'M-Pesa':
        if not validate_mpesa_number(details):
            await update.message.reply_text("❌ Invalid M-Pesa number format. Please try again.")
            return
        payment_data = {'phone': details}
    elif method == 'PayPal':
        if not validate_email(details):
            await update.message.reply_text("❌ Invalid email format. Please try again.")
            return
        payment_data = {'email': details}
    elif method == 'Bank':
        parts = details.split(',')
        if len(parts) < 3:
            await update.message.reply_text("❌ Invalid format. Please provide all required details.")
            return
        payment_data = {
            'bank_name': parts[0].strip(),
            'account_name': parts[1].strip(),
            'account_number': parts[2].strip()
        }
    
    # Get database instance
    db = get_db()
    
    # Update user profile with MongoDB
    db.users.update_one(
        {"user_id": user_id},
        {"$set": {f"payment_methods.{method}": payment_data}}
    )
    
    await update.message.reply_text(
        f"✅ {method} details saved successfully!\n"
        "You can now use this method for OTC withdrawals."
    )

# ================
# ERROR HANDLERS
# ================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors in the telegram bot"""
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    # Send error message to user
    if update and isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ An error occurred. Please try again later or contact support."
        )
    
    # Notify admin with detailed error
    if Config.ADMIN_ID:
        try:
            error_trace = context.error.__traceback__ if context.error else None
            error_details = f"⚠️ Bot error:\n{context.error}\n\nTraceback:\n{error_trace}"
            
            # Truncate if too long
            if len(error_details) > 3000:
                error_details = error_details[:3000] + "..."
                
            await context.bot.send_message(
                chat_id=Config.ADMIN_ID,
                text=error_details
            )
        except Exception as e:
            logger.error(f"Failed to notify admin about error: {e}")

# Add these callback handlers
async def affiliate_program(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show affiliate program information"""
    query = update.callback_query
    await query.answer()
    
    # Get affiliate stats
    stats = await telegram_client.get_affiliate_stats()
    
    if stats:
        text = "🤝 Affiliate Program\n\n"
        text += f"• Total Referrals: {stats.participants}\n"
        text += f"• Total Earnings: {stats.revenue} Stars\n"
        text += f"• Commission Rate: {stats.commission_permille}‰\n\n"
        text += "Share your referral link to earn commissions!"
        
        keyboard = [
            [InlineKeyboardButton("📋 Copy Referral Link", callback_data="affiliate_copy_link")],
            [InlineKeyboardButton("📊 View Detailed Stats", callback_data="affiliate_stats")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_main")]
        ]
    else:
        text = "Join our affiliate program to earn commissions!\n\n"
        text += "Share your unique referral link and earn Stars when your friends make purchases."
        
        keyboard = [
            [InlineKeyboardButton("🚀 Join Affiliate Program", callback_data="affiliate_join")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_main")]
        ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def join_affiliate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Join the affiliate program"""
    query = update.callback_query
    await query.answer()
    
    result = await telegram_client.join_affiliate_program("CryptoGamerBot")
    
    if result:
        # Get the referral link
        referral_link = result.connected_bots[0].url
        
        await query.edit_message_text(
            f"✅ You've joined our affiliate program!\n\n"
            f"Your referral link:\n`{referral_link}`\n\n"
            f"Share this link to earn commissions on your friends' purchases.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 Copy Link", callback_data=f"copy_{referral_link}")],
                [InlineKeyboardButton("📊 View Stats", callback_data="affiliate_stats")]
            ])
        )
    else:
        await query.edit_message_text(
            "❌ Could not join affiliate program at this time. Please try again later.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="affiliate_program")]
            ])
        )

async def handle_giveaway_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show giveaway creation options"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🎁 Premium Giveaway", callback_data="giveaway_premium")],
        [InlineKeyboardButton("⭐ Stars Giveaway", callback_data="giveaway_stars")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_main")]
    ]
    
    await query.edit_message_text(
        "🎉 Create a Giveaway\n\n"
        "Choose the type of giveaway to create:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_premium_giveaway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle premium giveaway creation"""
    query = update.callback_query
    await query.answer()
    
    # Implementation for premium giveaway
    from src.features.monetization.giveaways import giveaway_manager
    result = await giveaway_manager.create_premium_giveaway(
        user_id=query.from_user.id,
        boost_peer=types.InputPeerSelf(),  # Or specific channel
        users_count=10,
        months=3
    )
    
    if result['success']:
        await query.edit_message_text("✅ Premium giveaway created successfully!")
    else:
        await query.edit_message_text(f"❌ Error: {result['error']}")

async def handle_gift_sending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle gift sending"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('_')
    gift_id = data[2]
    recipient_id = data[3]
    
    from src.features.monetization.gifts import gift_manager
    result = await gift_manager.send_star_gift(
        user_id=query.from_user.id,
        recipient_id=recipient_id,
        gift_id=int(gift_id)
    )
    
    if result['success']:
        await query.edit_message_text("🎁 Gift sent successfully!")
    else:
        await query.edit_message_text(f"❌ Error sending gift: {result['error']}")

async def handle_attach_menu_install(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle attachment menu installation"""
    query = update.callback_query
    await query.answer()
    
    bot_id = query.data.split('_')[2]
    user_id = query.from_user.id
    
    try:
        # Check if disclaimer is needed
        bot_info = await telegram_client.get_attach_menu_bot(bot_id)
        
        if bot_info.get('side_menu_disclaimer_needed', False):
            # Show TOS disclaimer
            keyboard = [
                [InlineKeyboardButton("✅ Accept TOS", callback_data=f"attach_accept_{bot_id}")],
                [InlineKeyboardButton("❌ Cancel", callback_data="attach_cancel")]
            ]
            
            await query.edit_message_text(
                "📋 Terms of Service Agreement\n\n"
                "This Mini App is not affiliated with Telegram. By installing, you agree to our:\n"
                "• [Mini Apps TOS](https://telegram.org/tos/mini-apps)\n"
                "• [Privacy Policy](https://telegram.org/privacy)\n\n"
                "Do you accept these terms?",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            # Install directly
            await install_attach_menu(user_id, bot_id)
            
    except Exception as e:
        logger.error(f"Error installing attachment menu: {str(e)}")
        await query.edit_message_text("❌ Failed to install. Please try again.")

async def install_attach_menu(user_id: int, bot_id: int):
    """Install attachment menu for user"""
    try:
        result = await telegram_client(
            functions.messages.ToggleBotInAttachMenuRequest(
                bot=types.InputUser(user_id=bot_id, access_hash=0),  # Will be filled by client
                enabled=True
            )
        )
        
        if result:
            # Update user data
            db.users.update_one(
                {"user_id": user_id},
                {"$set": {"attach_menu_enabled": True}}
            )
            
            return True
        return False
        
    except Exception as e:
        logger.error(f"Error in attach menu installation: {str(e)}")
        return False
    
# Add sabotage callback handlers
async def handle_sabotage_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle player joining a sabotage game"""
    query = update.callback_query
    await query.answer()
    
    game_id = query.data.split('_')[2]
    user_id = query.from_user.id
    user_name = query.from_user.first_name
    
    # Add player to game
    from src.database.mongo import get_sabotage_game, update_sabotage_game
    game_data = get_sabotage_game(game_id)
    
    if not game_data:
        await query.edit_message_text("Game not found or already started.")
        return
    
    if user_id in game_data.get('players', {}):
        await query.answer("You've already joined this game!")
        return
    
    # Add player to game
    game_data['players'][str(user_id)] = {
        'name': user_name,
        'ready': False
    }
    
    update_sabotage_game(game_id, game_data)
    
    # Update message with current players
    player_list = "\n".join([f"• {p['name']}" for p in game_data['players'].values()])
    await query.edit_message_text(
        f"🎮 Crypto Crew: Sabotage\n\n"
        f"Players joined ({len(game_data['players'])}/6):\n{player_list}\n\n"
        "Game starts automatically when 6 players join.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Join Game", callback_data=f"sabotage_join_{game_id}")],
            [InlineKeyboardButton("Game Rules", callback_data="sabotage_rules")]
        ])
    )
    
    # Start game if we have 6 players
    if len(game_data['players']) == 6:
        # Initialize game
        game = SabotageGame(game_id, game_data['chat_id'])
        for player_id in game_data['players']:
            await game.add_player(player_id, game_data['players'][player_id]['name'])
        
        # Update game state
        game_data['state'] = 'tasks'
        game_data['start_time'] = datetime.now()
        game_data['end_time'] = datetime.now() + timedelta(minutes=15)
        update_sabotage_game(game_id, game_data)
        
        # Notify players
        for player_id in game_data['players']:
            try:
                role = "Miner" if game.players[player_id]['role'] == 'miner' else "Saboteur"
                await context.bot.send_message(
                    chat_id=player_id,
                    text=f"🎮 Game starting! You are a {role}.\n\n"
                         f"Open the miniapp to play: https://t.me/YourBotName/sabotage?game_id={game_id}"
                )
            except Exception as e:
                logger.error(f"Failed to notify player {player_id}: {str(e)}")