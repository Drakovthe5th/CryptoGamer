from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from firebase_admin import firestore  # Fixed import
from src.database.firebase import (
    create_user, get_user_balance, update_balance, get_user_data,
    users_ref, update_leaderboard_points, get_leaderboard, get_user_rank
)
from src.features.quests import get_active_quests
from src.utils.conversions import to_xno
from config import Config
import datetime
import random
import logging  # Added missing import

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user.id
    username = user.username or user.first_name or "Anonymous"
    
    # Create user if doesn't exist
    create_user(user_id, username)
    
    # Handle referral
    if context.args:
        try:
            referrer_id = int(context.args[0])
            if referrer_id != user_id:
                # Award referrer
                update_balance(referrer_id, Config.REWARDS['referral'])
                update_leaderboard_points(referrer_id, 50)
                
                # Update referral count
                user_ref = users_ref.document(str(referrer_id))
                user_ref.update({'referral_count': firestore.Increment(1)})
                
                # Notify referrer
                try:
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text=f"🎉 {username} joined using your referral link! "
                             f"You earned {Config.REWARDS['referral']:.6f} XNO"
                    )
                except Exception:
                    pass
        except ValueError:
            pass
    
    # Welcome message
    text = (
        f"👋 Welcome to CryptoGameBot, {user.first_name}!\n\n"
        "🎮 Earn cryptocurrency by playing games:\n"
        "• 🧠 Trivia quizzes\n"
        "• 💥 Clicker game\n"
        "• 🎰 Spin wheel\n"
        "• 🎯 Complete quests\n\n"
        "💰 Withdraw your earnings to Nano, M-Pesa, or PayPal!\n\n"
        "🆓 Claim free crypto with /faucet\n"
        "🏆 Compete on the /leaderboard\n"
        "💼 Open in-app with /app"
    )
    
    # Start buttons
    keyboard = [
        [InlineKeyboardButton("🎮 Play Games", callback_data="play")],
        [InlineKeyboardButton("💰 Withdraw", callback_data="withdraw")],
        [InlineKeyboardButton("🎯 Quests", callback_data="quests")]
    ]
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    balance = get_user_balance(user_id)
    
    text = (
        f"💰 Your Balance: {to_xno(balance):.6f} XNO\n\n"
        f"💸 Minimum withdrawal: {Config.MIN_WITHDRAWAL} XNO\n"
        "💳 Set up withdrawal methods with /set_withdrawal"
    )
    
    await update.message.reply_text(text)

async def play_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Game selection keyboard
    keyboard = [
        [InlineKeyboardButton("🧠 Trivia Quiz", callback_data="trivia")],
        [InlineKeyboardButton("💥 Clicker Game", callback_data="clicker")],
        [InlineKeyboardButton("🎰 Spin Wheel", callback_data="spin")],
        [InlineKeyboardButton("🎁 Daily Bonus", callback_data="daily")]
    ]
    
    await update.message.reply_text(
        "🎮 Choose a game to play:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    balance = get_user_balance(user_id)
    
    if balance < Config.MIN_WITHDRAWAL:
        await update.message.reply_text(
            f"❌ Minimum withdrawal: {Config.MIN_WITHDRAWAL} XNO\n"
            f"Your balance: {to_xno(balance):.6f} XNO"
        )
        return
    
    # Withdrawal methods
    keyboard = [
        [InlineKeyboardButton("🌐 Nano", callback_data="withdraw_nano")],
        [InlineKeyboardButton("📱 M-Pesa", callback_data="withdraw_mpesa")],
        [InlineKeyboardButton("💳 PayPal", callback_data="withdraw_paypal")],
        [InlineKeyboardButton("❌ Cancel", callback_data="withdraw_cancel")]
    ]
    
    await update.message.reply_text(
        "💸 Select withdrawal method:",
        reply_markup=InlineKeyboardMarkup(keyboard))
    

async def miniapp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    miniapp_url = f"https://{Config.RENDER_URL}/miniapp"
    text = (
        "📲 Open the CryptoGameBot MiniApp for a better gaming experience!\n\n"
        f"👉 [Launch MiniApp]({miniapp_url})\n\n"
        "Play games, check balance, and withdraw directly in-app!"
    )
    
    await update.message.reply_text(
        text, 
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    leaderboard = get_leaderboard(10)
    text = "🏆 <b>TOP PLAYERS</b>\n\n"
    
    for idx, user in enumerate(leaderboard, start=1):
        text += f"{idx}. {user.get('username', 'Anonymous')} - {user.get('points', 0)} pts\n"
    
    # Add current user position
    user_rank = get_user_rank(update.effective_user.id)
    text += f"\n👤 Your position: #{user_rank}"
    
    await update.message.reply_text(text, parse_mode='HTML')

async def show_quests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    for quest in get_active_quests():
        quest_data = quest.to_dict()
        keyboard.append([InlineKeyboardButton(
            quest_data['title'], 
            callback_data=f"quest_{quest.id}"
        )])
    
    await update.message.reply_text(
        "🎯 Available Quests:",
        reply_markup=InlineKeyboardMarkup(keyboard))
    

async def faucet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /faucet command"""
    user_id = update.effective_user.id
    now = datetime.datetime.now()
    user_data = get_user_data(user_id)
    
    # Check last claim time
    last_claim = user_data.get('faucet_claimed')
    if last_claim and (now - last_claim).seconds < Config.FAUCET_COOLDOWN * 3600:
        hours_left = Config.FAUCET_COOLDOWN - (now - last_claim).seconds // 3600
        await update.message.reply_text(
            f"⏳ You can claim again in {hours_left} hours!"
        )
        return
    
    # Award faucet
    reward = Config.REWARDS['faucet']
    new_balance = update_balance(user_id, reward)
    
    # Update last claim time
    user_ref = users_ref.document(str(user_id))
    user_ref.update({'faucet_claimed': now})
    
    await update.message.reply_text(
        f"💧 You claimed {reward:.6f} XNO!\n"
        f"💰 New balance: {to_xno(new_balance):.6f} XNO"
    )

async def set_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /set_withdrawal command"""
    keyboard = [
        [InlineKeyboardButton("🌐 Set Nano Address", callback_data="set_nano")],
        [InlineKeyboardButton("📱 Set M-Pesa Number", callback_data="set_mpesa")],
        [InlineKeyboardButton("💳 Set PayPal Email", callback_data="set_paypal")]
    ]
    
    await update.message.reply_text(
        "🔐 Select a withdrawal method to set up:",
        reply_markup=InlineKeyboardMarkup(keyboard))
    

async def weekend_promotion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.datetime.now()
    is_weekend = today.weekday() in [5, 6]  # Saturday or Sunday
    
    if is_weekend:
        text = (
            "🎉 WEEKEND SPECIAL 🎉\n\n"
            "All ad rewards are boosted by 50% this weekend!\n\n"
            "🔥 Earn more crypto with every ad you watch\n"
            "🚀 Available in the MiniApp now!"
        )
    else:
        text = (
            "🔥 Next Weekend Promotion 🔥\n\n"
            "Starting Saturday, all ad rewards will be boosted by 50%!\n"
            "Set a reminder to maximize your earnings."
        )
    
    keyboard = [
        [InlineKeyboardButton("🚀 Open MiniApp", url=f"https://{Config.RENDER_URL}/miniapp")]
    ]
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard))