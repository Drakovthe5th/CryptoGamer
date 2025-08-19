import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.database.mongo import (
    get_user_data, update_balance, update_leaderboard_points, 
    get_db, SERVER_TIMESTAMP
)
from src.features.otc_desk import otc_desk
from src.features.quests import complete_quest
from src.integrations.tonE2 import process_ton_withdrawal
from src.utils.conversions import to_ton, convert_currency, calculate_fee, game_coins_to_ton
from src.utils.validators import validate_ton_address, validate_mpesa_number, validate_email
from config import Config
import random
import datetime
import logging

logger = logging.getLogger(__name__)
db = get_db()
quests_collection = db.quests

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
    
    # Update last played time
    users_db.document(str(user_id)).update({
        'last_played.trivia': SERVER_TIMESTAMP
    })
    
    if selected == correct_idx:
        # Correct answer
        reward = Config.REWARDS['trivia_correct']
        new_balance = update_balance(user_id, reward)
        update_leaderboard_points(user_id, 5)
        
        await query.edit_message_text(
            f"✅ Correct! You earned {reward:.6f} TON\n"
            f"💰 New balance: {to_ton(new_balance):.6f} TON"
        )
    else:
        # Incorrect answer
        reward = Config.REWARDS.get('trivia_incorrect', 0.001)
        new_balance = update_balance(user_id, reward)
        
        correct_answer = question['options'][correct_idx]
        await query.edit_message_text(
            f"❌ Wrong! The correct answer was: {correct_answer}\n"
            f"💡 You still earned {reward:.6f} TON for playing!\n"
            f"💰 New balance: {to_ton(new_balance):.6f} TON"
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
    
    # Update last played time
    users_db.document(str(user_id)).update({
        'last_played.spin': SERVER_TIMESTAMP
    })
    
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
        f"💎 New balance: {to_ton(new_balance):.6f} TON"
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
    payment_details = user_data['payment_methods'].get(method, {})
    
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
    
    deal_db = otc_deals_db.add(deal_data)
    deal_id = deal_db[1].id
    
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
    amount = context.user_data['withdrawal_amount']
    ton_amount = game_coins_to_ton(amount_gc)
    
    if not validate_ton_address(address):
        await update.message.reply_text("❌ Invalid TON address format. Please try again.")
        return
    
        # Deduct game coins and process TON withdrawal
    update_game_coins(user_id, -amount_gc)
    result = process_ton_withdrawal(user_id, ton_amount, address)
    
    if result and result.get('status') == 'success':
        withdrawal_data = {
            'user_id': user_id,
            'amount': amount,
            'address': address,
            'tx_hash': result['tx_hash'],
            'status': 'pending',
            'created_at': SERVER_TIMESTAMP
        }
        withdrawals_db.add(withdrawal_data)
        update_balance(user_id, -amount)
        
        await update.message.reply_text(
            f"✅ Withdrawal of {amount:.6f} TON is processing!\n"
            f"Transaction: https://tonscan.org/tx/{result.get('tx_hash')}"
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
    
    # Get quest details
    quest_doc = db.quests.find_one({"_id": quest_id})
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
    if quest_id in user_data.get('completed_quests', {}):
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
    
    # Update user profile
    user_db = users_db.document(str(user_id))
    user_db.update({
        f'payment_methods.{method}': payment_data
    })
    
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