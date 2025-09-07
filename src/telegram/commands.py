from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from pymongo import MongoClient
from src.database.mongo import (
    create_user, get_user_balance, update_balance, get_user_data,
    update_leaderboard_points, get_leaderboard, get_user_rank, db
)
from src.features.quests import get_active_quests
from src.utils.conversions import game_coins_to_ton
from src.utils.conversions import ton_to_game_coins
from games.sabotage_game import SabotageGame
from games.chess_game import ChessGame
from games.pool_game import PoolGame
from games.poker_game import PokerGame
from games.mini_royal import MiniRoyalGame
from config import Config
import datetime
import random
import logging
import time

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
                db.users.update_one(
                    {"user_id": referrer_id},
                    {"$inc": {"referral_count": 1}}
                )
                
                # Notify referrer
                try:
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text=f"🎉 {username} joined using your referral link! "
                             f"You earned {Config.REWARDS['referral']:.6f} TON"
                    )
                except Exception:
                    pass
        except ValueError:
            pass
    
    # Welcome message with TON focus
    text = (
        f"👋 Welcome to CryptoGameBot, {user.first_name}!\n\n"
        "💎 Earn TON cryptocurrency by:\n"
        "• 🧠 Playing trivia games\n"
        "• 🎰 Spinning the wheel\n"
        "• 📺 Watching ads\n"
        "• 🎯 Completing quests\n"
        "• ♟️ Playing premium games\n\n"
        "💰 Withdraw to your TON wallet or convert to cash via our OTC desk!\n\n"
        "🆓 Claim free TON with /faucet\n"
        "🏆 Compete on the /leaderboard\n"
        "📱 Open in-app with /app"
    )
    
    # Start buttons
    keyboard = [
        [InlineKeyboardButton("🎮 Play Games", callback_data="play")],
        [InlineKeyboardButton("💰 Withdraw", callback_data="withdraw")],
        [InlineKeyboardButton("🎯 Quests", callback_data="quests")],
        [InlineKeyboardButton("♟️ Premium Games", callback_data="premium_games")]
    ]
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    game_coins = user_data.get('game_coins', 0)
    ton_equivalent = game_coins_to_ton(game_coins)
    
    text = (
        f"🎮 Game Coins: {game_coins:,} GC\n"
        f"💎 TON Equivalent: {ton_equivalent:.6f} TON\n\n"
        f"💸 Minimum Withdrawal: 200,000 GC (100 TON)\n"
        "💳 Set up withdrawal methods with /set_withdrawal"
    )
    
    await update.message.reply_text(text)

async def play_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Game selection keyboard - Free games
    keyboard = [
        [InlineKeyboardButton("🧠 Trivia Quiz", callback_data="trivia")],
        [InlineKeyboardButton("🎰 Spin Wheel", callback_data="spin")],
        [InlineKeyboardButton("🖱️ Click Game", callback_data="clicker")],
        [InlineKeyboardButton("🦖 T-Rex Runner", callback_data="trex")],
        [InlineKeyboardButton("🏄 Edge Surf", callback_data="edge_surf")],
        [InlineKeyboardButton("♟️ Premium Games", callback_data="premium_games")],
        [InlineKeyboardButton("🎁 Daily Bonus", callback_data="daily")]
    ]
    
    await update.message.reply_text(
        "🎮 Choose a game to play:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def premium_games(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show premium games selection"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    
    # Check if user has premium access
    has_premium = user_data.get('is_premium', False)
    
    keyboard = [
        [InlineKeyboardButton("🕵️ Crypto Crew: Sabotage", callback_data="sabotage")],
        [InlineKeyboardButton("🎯 Mini Royal", callback_data="mini_royal")],
        [InlineKeyboardButton("♟️ Chess Masters", callback_data="chess")],
        [InlineKeyboardButton("🎱 Pool Game", callback_data="pool")],
        [InlineKeyboardButton("🃏 Poker Game", callback_data="poker")],
        [InlineKeyboardButton("⬅️ Back to Free Games", callback_data="play")]
    ]
    
    if not has_premium:
        text = (
            "♟️ <b>Premium Games</b>\n\n"
            "Unlock exclusive premium games with higher rewards!\n\n"
            "⭐ Premium features:\n"
            "• Higher earning potential\n"
            "• Exclusive game modes\n"
            "• Multiplayer competitions\n"
            "• Tournament prizes\n\n"
            "Get premium access through the MiniApp or by purchasing with Telegram Stars!"
        )
    else:
        text = (
            "♟️ <b>Premium Games</b>\n\n"
            "Choose from our exclusive premium games:\n\n"
            "• 🕵️ Crypto Crew: Sabotage - Social deduction game\n"
            "• 🎯 Mini Royal - Battle royale style game\n"
            "• ♟️ Chess Masters - Competitive chess\n"
            "• 🎱 Pool Game - 8-ball pool tournament\n"
            "• 🃏 Poker Game - Texas Hold'em poker\n\n"
            "Earn up to 10x more TON in premium games!"
        )
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    balance = get_user_balance(user_id)
    
    if balance < Config.MIN_WITHDRAWAL:
        await update.message.reply_text(
            f"❌ Minimum withdrawal: {Config.MIN_WITHDRAWAL} TON\n"
            f"Your balance: {game_coins_to_ton(balance):.6f} TON"
        )
        return
    
    # Withdrawal methods - TON and OTC options
    keyboard = [
        [InlineKeyboardButton("💎 TON Wallet", callback_data="withdraw_ton")],
        [InlineKeyboardButton("💵 Cash via OTC", callback_data="withdraw_cash")],
        [InlineKeyboardButton("❌ Cancel", callback_data="withdraw_cancel")]
    ]
    
    await update.message.reply_text(
        "💸 Select withdrawal method:",
        reply_markup=InlineKeyboardMarkup(keyboard))
    

async def miniapp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    miniapp_url = f"https://{Config.RENDER_URL}/miniapp"
    text = (
        "📲 Open the CryptoGameBot MiniApp for the best experience!\n\n"
        "Features:\n"
        "• 💎 Real-time TON balance\n"
        "• 🎮 Play TON-earning games\n"
        "• ♟️ Premium games access\n"
        "• 💸 Seamless withdrawals\n"
        "• 📊 View leaderboards\n\n"
        f"👉 [Launch MiniApp]({miniapp_url})"
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
    db.users.update_one(
        {"user_id": user_id},
        {"$set": {'faucet_claimed': now}}
    )
    
    await update.message.reply_text(
        f"💧 You claimed {reward:.6f} TON!\n"
        f"💰 New balance: {game_coins_to_ton(new_balance):.6f} TON"
    )

async def set_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /set_withdrawal command"""
    keyboard = [
        [InlineKeyboardButton("💎 Set TON Address", callback_data="set_ton")],
        [InlineKeyboardButton("📱 Set M-Pesa Number", callback_data="set_mpesa")],
        [InlineKeyboardButton("💳 Set PayPal Email", callback_data="set_paypal")],
        [InlineKeyboardButton("🏦 Set Bank Details", callback_data="set_bank")]
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
            "All rewards are boosted by 50% this weekend!\n\n"
            "🔥 Earn more TON with every action\n"
            "♟️ Premium games have 2x rewards!\n"
            "🚀 Available in the MiniApp now!"
        )
    else:
        text = (
            "🔥 Next Weekend Promotion 🔥\n\n"
            "Starting Saturday, all rewards will be boosted by 50%!\n"
            "Premium games will have 2x rewards!\n"
            "Set a reminder to maximize your TON earnings."
        )
    
    keyboard = [
        [InlineKeyboardButton("🚀 Open MiniApp", url=f"https://{Config.RENDER_URL}/miniapp")]
    ]
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard))

async def otc_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show OTC desk information"""
    text = (
        "💱 <b>OTC Desk Information</b>\n\n"
        "Convert your TON to cash quickly and securely:\n\n"
        "• 💵 Supported currencies: USD, EUR, KES\n"
        "• 💳 Payment methods: M-Pesa, PayPal, Bank Transfer\n"
        "• ⚡ Fast processing: Within 24 hours\n"
        "• 🔒 Secure transactions\n\n"
        "To get started:\n"
        "1. Use /withdraw and select 'Cash via OTC'\n"
        "2. Choose your preferred currency\n"
        "3. Enter your payment details\n\n"
        "Set up your payment methods with /set_withdrawal"
    )
    
    await update.message.reply_text(text, parse_mode='HTML')

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show support information"""
    text = (
        "🆘 <b>Support Center</b>\n\n"
        "Need help? Here's how to reach us:\n\n"
        "• 📧 Email: support@cryptogamebot.com\n"
        "• 💬 Telegram: @CryptoGameSupport\n"
        "• 🌐 Website: https://cryptogamebot.com/support\n\n"
        "Common issues:\n"
        "- Withdrawal delays: Can take up to 24 hours\n"
        "- Missing rewards: Check your transaction history\n"
        "- Game issues: Try reloading the MiniApp\n"
        "- Premium access: Contact support for assistance\n\n"
        "For faster assistance, include your user ID:\n"
        f"<code>{update.effective_user.id}</code>"
    )
    
    await update.message.reply_text(text, parse_mode='HTML')

async def gifts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show available gifts"""
    from src.features.monetization.gifts import gift_manager
    result = await gift_manager.get_available_gifts()
    
    if result['success']:
        keyboard = []
        for gift in result['gifts'].gifts:
            keyboard.append([
                InlineKeyboardButton(
                    f"{gift.stars} Stars Gift",
                    callback_data=f"gift_send_{gift.id}_{update.effective_user.id}"
                )
            ])
        
        await update.message.reply_text(
            "🎁 Available Gifts:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text("❌ Could not load gifts")

async def my_gifts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's received gifts"""
    from src.features.monetization.gifts import gift_manager
    result = await gift_manager.get_user_gifts(update.effective_user.id)
    
    if result['success']:
        text = "🎁 Your Received Gifts:\n\n"
        for gift in result['gifts'].gifts:
            text += f"• {gift.gift.stars} Stars Gift\n"
        
        await update.message.reply_text(text)
    else:
        await update.message.reply_text("❌ Could not load your gifts")

# Premium game commands
async def sabotage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a sabotage game in a group"""
    chat_id = update.effective_chat.id
    
    # Check if in a group
    if update.effective_chat.type not in ['group', 'supergroup']:
        await update.message.reply_text(
            "Sabotage can only be played in groups!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Create a Group", callback_data="create_group")]
            ])
        )
        return
    
    # Create new game
    game_id = f"sabotage_{chat_id}_{int(time.time())}"
    game = SabotageGame(game_id, str(chat_id))
    
    # Save to database
    from src.database.mongo import save_sabotage_game
    save_sabotage_game(game.to_dict())
    
    # Send invitation message
    keyboard = [
        [InlineKeyboardButton("Join Game", callback_data=f"sabotage_join_{game_id}")],
        [InlineKeyboardButton("Game Rules", callback_data="sabotage_rules")]
    ]
    
    await update.message.reply_text(
        "🎮 Crypto Crew: Sabotage\n\n"
        "A social deduction game where miners try to complete tasks while saboteurs "
        "try to steal gold without getting caught!\n\n"
        "Click 'Join Game' to participate. Game starts when 6 players join.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def chess_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a chess game"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    
    if not user_data.get('is_premium', False):
        await update.message.reply_text(
            "♟️ Chess Masters is a premium game!\n\n"
            "Upgrade to premium to play competitive chess and earn higher rewards.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Get Premium", callback_data="get_premium")],
                [InlineKeyboardButton("Free Games", callback_data="play")]
            ])
        )
        return
    
    # Start chess game
    game = ChessGame()
    game_id = game.create_game(user_id)
    
    keyboard = [
        [InlineKeyboardButton("Play Now", callback_data=f"chess_play_{game_id}")],
        [InlineKeyboardButton("Invite Friend", callback_data=f"chess_invite_{game_id}")]
    ]
    
    await update.message.reply_text(
        "♟️ Chess Masters\n\n"
        "Play competitive chess against other players!\n"
        "• Win up to 5000 GC per game\n"
        "• ELO rating system\n"
        "• Tournament rewards\n\n"
        "Click 'Play Now' to find an opponent!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def pool_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a pool game"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    
    if not user_data.get('is_premium', False):
        await update.message.reply_text(
            "🎱 Pool Game is a premium game!\n\n"
            "Upgrade to premium to play 8-ball pool tournaments.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Get Premium", callback_data="get_premium")],
                [InlineKeyboardButton("Free Games", callback_data="play")]
            ])
        )
        return
    
    keyboard = [
        [InlineKeyboardButton("Quick Match", callback_data="pool_quick")],
        [InlineKeyboardButton("Create Tournament", callback_data="pool_tournament")],
        [InlineKeyboardButton("Practice Mode", callback_data="pool_practice")]
    ]
    
    await update.message.reply_text(
        "🎱 Pool Masters\n\n"
        "Play 8-ball pool against other players!\n"
        "• Win up to 5000 GC per game\n"
        "• Tournament prizes\n"
        "• Practice mode available\n\n"
        "Choose your game mode:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def poker_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a poker game"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    
    if not user_data.get('is_premium', False):
        await update.message.reply_text(
            "🃏 Poker Game is a premium game!\n\n"
            "Upgrade to premium to play Texas Hold'em poker.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Get Premium", callback_data="get_premium")],
                [InlineKeyboardButton("Free Games", callback_data="play")]
            ])
        )
        return
    
    keyboard = [
        [InlineKeyboardButton("Join Table", callback_data="poker_join")],
        [InlineKeyboardButton("Create Table", callback_data="poker_create")],
        [InlineKeyboardButton("Tournaments", callback_data="poker_tournaments")]
    ]
    
    await update.message.reply_text(
        "🃏 Poker Royale\n\n"
        "Play Texas Hold'em poker with real stakes!\n"
        "• Win up to 10000 GC per game\n"
        "• Tournament series\n"
        "• Sit & Go tables\n\n"
        "Choose your game:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def mini_royal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a mini royal game"""
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    
    if not user_data.get('is_premium', False):
        await update.message.reply_text(
            "🎯 Mini Royal is a premium game!\n\n"
            "Upgrade to premium to play battle royale style games.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Get Premium", callback_data="get_premium")],
                [InlineKeyboardButton("Free Games", callback_data="play")]
            ])
        )
        return
    
    keyboard = [
        [InlineKeyboardButton("Join Game", callback_data="mini_royal_join")],
        [InlineKeyboardButton("Create Squad", callback_data="mini_royal_squad")]
    ]
    
    await update.message.reply_text(
        "🎯 Mini Royal\n\n"
        "Battle royale style game with last-man-standing gameplay!\n"
        "• Win up to 8000 GC per game\n"
        "• Squad gameplay\n"
        "• Unique power-ups\n\n"
        "Join a game or create your squad:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )