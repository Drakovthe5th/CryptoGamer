from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from firebase_admin import firestore  # Fixed import
from src.database.firebase import (
    get_user_data, update_balance, update_leaderboard_points, 
    quests_ref, users_ref, SERVER_TIMESTAMP
)
from src.features.withdrawal import process_withdrawal
from src.features.quests import complete_quest
from src.utils.conversions import to_xno
from config import Config
import random
import datetime
import logging

logger = logging.getLogger(__name__)

async def set_nano_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt user to set Nano address"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['awaiting_nano'] = True
    await query.edit_message_text(
        "🌐 Please send your Nano address in the following format:\n"
        "`nano_1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcd`\n\n"
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
    
    # Trivia questions
    questions = [
        {
            "question": "What consensus algorithm does Nano use?",
            "options": ["Proof of Work", "Proof of Stake", "Block Lattice", "Directed Acyclic Graph"],
            "correct": 2
        },
        {
            "question": "What is the smallest unit of Nano called?",
            "options": ["Nano", "Raw", "Wei", "Satoshi"],
            "correct": 1
        },
        {
            "question": "When was Nano (then RaiBlocks) created?",
            "options": ["2014", "2015", "2016", "2017"],
            "correct": 1
        }
    ]
    
    # Select random question
    question = random.choice(questions)
    context.user_data['trivia_question'] = question  # Store for answer handling
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
    question = context.user_data.get('trivia_question')  # Get stored question
    
    # Update last played time
    users_ref.document(str(user_id)).update({
        'last_played.trivia': SERVER_TIMESTAMP
    })
    
    if selected == correct_idx:
        # Correct answer
        reward = Config.REWARDS['trivia_correct']
        new_balance = update_balance(user_id, reward)
        update_leaderboard_points(user_id, 5)
        
        await query.edit_message_text(
            f"✅ Correct! You earned {reward:.6f} XNO\n"
            f"💰 New balance: {to_xno(new_balance):.6f} XNO"
        )
    else:
        # Incorrect answer
        reward = Config.REWARDS.get('trivia_incorrect', 0.001)
        new_balance = update_balance(user_id, reward)
        
        # Use stored question for correct answer
        correct_answer = question['options'][correct_idx]
        await query.edit_message_text(
            f"❌ Wrong! The correct answer was: {correct_answer}\n"
            f"💡 You still earned {reward:.6f} XNO for playing!\n"
            f"💰 New balance: {to_xno(new_balance):.6f} XNO"
        )

async def clicker_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start clicker game session"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    context.user_data['clicker_score'] = 0
    context.user_data['clicker_start'] = datetime.datetime.now()
    
    keyboard = [
        [InlineKeyboardButton("💥 CLICK ME!", callback_data="clicker_click")],
        [InlineKeyboardButton("🏆 FINISH", callback_data="clicker_finish")]
    ]
    
    await query.edit_message_text(
        "💥 CLICKER GAME!\n\n"
        "Click as fast as you can for 30 seconds!\n"
        "Current clicks: 0",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user click in clicker game"""
    query = update.callback_query
    await query.answer()
    
    clicker_data = context.user_data
    
    # Increment score
    clicker_data['clicker_score'] += 1
    
    # Update message with current score
    elapsed = (datetime.datetime.now() - clicker_data['clicker_start']).seconds
    remaining = max(0, 30 - elapsed)
    
    await query.edit_message_text(
        f"💥 CLICKER GAME!\n\n"
        f"Click as fast as you can for {remaining} seconds!\n"
        f"Current clicks: {clicker_data['clicker_score']}",
        reply_markup=query.message.reply_markup
    )

async def finish_clicker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finish clicker game and award points"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    score = context.user_data.get('clicker_score', 0)
    
    # Calculate reward
    reward = Config.REWARDS['clicker_click'] * score
    new_balance = update_balance(user_id, reward)
    update_leaderboard_points(user_id, score // 10)  # 1 point per 10 clicks
    
    # Update last played time
    users_ref.document(str(user_id)).update({
        'last_played.clicker': SERVER_TIMESTAMP
    })
    
    await query.edit_message_text(
        f"🏁 Game finished!\n"
        f"🔥 Total clicks: {score}\n"
        f"💰 You earned: {reward:.6f} XNO\n"
        f"💎 New balance: {to_xno(new_balance):.6f} XNO"
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
        "Test your luck and win up to 0.1 XNO!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def spin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process wheel spin"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Update last played time
    users_ref.document(str(user_id)).update({
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
        f"💰 You earned: {reward:.6f} XNO\n"
        f"💎 New balance: {to_xno(new_balance):.6f} XNO"
    )

async def daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Claim daily bonus"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    today = datetime.datetime.now().date()
    
    # Check if already claimed today
    last_claim = user_data.get('daily_claimed')
    if last_claim and last_claim.date() == today:
        await query.edit_message_text("⏳ You've already claimed your daily bonus today!")
        return
    
    # Award bonus
    reward = Config.REWARDS['daily_bonus']
    new_balance = update_balance(user_id, reward)
    update_leaderboard_points(user_id, 10)
    
    # Update claim time
    users_ref.document(str(user_id)).update({
        'daily_claimed': SERVER_TIMESTAMP
    })
    
    await query.edit_message_text(
        f"🎁 DAILY BONUS CLAIMED!\n\n"
        f"💰 You received: {reward:.6f} XNO\n"
        f"💎 New balance: {to_xno(new_balance):.6f} XNO\n\n"
        f"Come back tomorrow for another bonus!"
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
    
    if balance < Config.MIN_WITHDRAWAL:
        await query.edit_message_text(
            f"❌ Minimum withdrawal: {Config.MIN_WITHDRAWAL} XNO\n"
            f"Your balance: {balance:.6f} XNO"
        )
        return
        
    # Get withdrawal details
    method_data = user_data['withdrawal_methods'].get(method)
    if not method_data or not method_data.get('verified'):
        await query.edit_message_text(
            f"⚠️ Your {method} method is not verified. "
            "Please set it up first with /set_withdrawal"
        )
        return
        
    # Process withdrawal
    result = process_withdrawal(user_id, method, balance, method_data)
    
    if result and result.get('status') == 'success':
        update_balance(user_id, -balance)
        await query.edit_message_text(
            f"✅ Withdrawal of {balance:.6f} XNO to {method} is processing!\n"
            f"Transaction ID: {result.get('tx_id', 'N/A')}"
        )
    else:
        error = result.get('error', 'Unknown error') if result else 'Withdrawal failed'
        await query.edit_message_text(f"❌ Withdrawal failed: {error}")

# ================
# QUEST HANDLERS
# ================

async def quest_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show details of a specific quest"""
    query = update.callback_query
    await query.answer()
    quest_id = query.data.split('_')[1]
    
    # Get quest details
    quest_doc = quests_ref.document(quest_id).get()
    if not quest_doc.exists:
        await query.edit_message_text("Quest not found.")
        return
    
    quest_data = quest_doc.to_dict()
    
    # Format quest details
    text = f"<b>{quest_data['title']}</b>\n\n"
    text += f"{quest_data['description']}\n\n"
    text += f"💎 Reward: {quest_data['reward_xno']:.6f} XNO\n"
    text += f"⭐ Points: {quest_data['reward_points']}\n"
    text += f"🔁 Completions: {quest_data.get('completions', 0)}\n\n"
    
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

async def back_to_quests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to quest list view"""
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    quests = quests_ref.where('active', '==', True).stream()
    
    for quest in quests:
        quest_data = quest.to_dict()
        keyboard.append([InlineKeyboardButton(
            quest_data['title'], 
            callback_data=f"quest_{quest.id}"
        )])
    
    await query.edit_message_text(
        "🎯 Available Quests:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# =================
# NAVIGATION HANDLERS
# =================

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to main menu"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🎮 Play Games", callback_data="play")],
        [InlineKeyboardButton("💰 Withdraw", callback_data="withdraw")],
        [InlineKeyboardButton("🎯 Quests", callback_data="quests")]
    ]
    
    await query.edit_message_text(
        "🏠 Main Menu",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================
# ERROR HANDLERS
# ================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors in the telegram bot"""
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    if update and isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ An error occurred. Please try again later or contact support."
        )
    
    # Notify admin
    if Config.ADMIN_ID:
        try:
            await context.bot.send_message(
                chat_id=Config.ADMIN_ID,
                text=f"⚠️ Bot error:\n{context.error}"
            )
        except Exception:
            logger.error("Failed to notify admin about error")