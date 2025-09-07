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
from games.chess_game import ChessGame
from games.pool_game import PoolGame
from games.poker_game import PokerGame
from games.mini_royal import MiniRoyalGame
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
    "gift_convert": handle_gift_convert,
    "premium_games": "handle_premium_games_selection",
    "sabotage": "handle_sabotage_callback",
    "chess": "handle_chess_callback",
    "pool": "handle_pool_callback",
    "poker": "handle_poker_callback",
    "mini_royal": "handle_mini_royal_callback",
    "clicker": "handle_clicker_callback",
    "trex": "handle_trex_callback",
    "edge_surf": "handle_edge_surf_callback"
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
        # Win amount (0.01 to 0.1 TON)
        win_amount = random.uniform(0.01, 0.1)
        new_balance = update_balance(user_id, win_amount)
        update_leaderboard_points(user_id, 3)
        
        await query.edit_message_text(
            f"🎉 You won {win_amount:.6f} TON!\n"
            f"💰 New balance: {game_coins_to_ton(new_balance):.6f} TON"
        )
    else:
        # Small consolation
        consolation = Config.REWARDS.get('spin_consolation', 0.001)
        new_balance = update_balance(user_id, consolation)
        
        await query.edit_message_text(
            f"😢 No win this time, but you earned {consolation:.6f} TON for playing!\n"
            f"💰 New balance: {game_coins_to_ton(new_balance):.6f} TON"
        )

async def clicker_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start clicker game"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    
    # Check game cooldown
    last_played = user_data.get('last_played', {}).get('clicker')
    if last_played and (datetime.datetime.now() - last_played).seconds < Config.GAME_COOLDOWN * 60:
        cooldown = Config.GAME_COOLDOWN * 60 - (datetime.datetime.now() - last_played).seconds
        await query.edit_message_text(
            f"⏳ You can play clicker again in {cooldown // 60} minutes!"
        )
        return
    
    context.user_data['clicker_count'] = 0
    context.user_data['clicker_start'] = datetime.datetime.now()
    
    keyboard = [[InlineKeyboardButton("🖱️ CLICK ME!", callback_data="clicker_click")]]
    
    await query.edit_message_text(
        "🖱️ CLICKER GAME!\n\n"
        "Click as fast as you can for 10 seconds!\n"
        "Each click earns you 0.0001 TON!\n\n"
        "Ready? Click the button to start!",
        reply_markup=InlineKeyboardMarkup(keyboard))

async def clicker_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle clicker clicks"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    click_count = context.user_data.get('clicker_count', 0)
    start_time = context.user_data.get('clicker_start')
    
    if not start_time:
        # Game ended
        await query.edit_message_text("Game session expired! Start a new game.")
        return
    
    elapsed = (datetime.datetime.now() - start_time).seconds
    
    if elapsed >= 10:
        # Game over
        total_earned = click_count * 0.0001
        new_balance = update_balance(user_id, total_earned)
        update_leaderboard_points(user_id, click_count // 10)
        
        # Update last played time
        db = get_db()
        db.users.update_one(
            {"user_id": user_id},
            {"$set": {"last_played.clicker": SERVER_TIMESTAMP}}
        )
        
        await query.edit_message_text(
            f"⏰ TIME'S UP!\n"
            f"🏆 Total clicks: {click_count}\n"
            f"💰 Earned: {total_earned:.6f} TON\n"
            f"💎 New balance: {game_coins_to_ton(new_balance):.6f} TON"
        )
        return
    
    # Increment click count
    context.user_data['clicker_count'] = click_count + 1
    current_clicks = context.user_data['clicker_count']
    
    keyboard = [[InlineKeyboardButton(f"🖱️ CLICK ME! ({current_clicks})", callback_data="clicker_click")]]
    
    await query.edit_message_text(
        f"🖱️ CLICKER GAME!\n\n"
        f"Clicks: {current_clicks}\n"
        f"Time left: {10 - elapsed} seconds\n"
        f"Earned: {current_clicks * 0.0001:.6f} TON",
        reply_markup=InlineKeyboardMarkup(keyboard))

async def trex_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start T-Rex runner game"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    
    # Check game cooldown
    last_played = user_data.get('last_played', {}).get('trex')
    if last_played and (datetime.datetime.now() - last_played).seconds < Config.GAME_COOLDOWN * 60:
        cooldown = Config.GAME_COOLDOWN * 60 - (datetime.datetime.now() - last_played).seconds
        await query.edit_message_text(
            f"⏳ You can play T-Rex again in {cooldown // 60} minutes!"
        )
        return
    
    keyboard = [[InlineKeyboardButton("🦖 PLAY T-REX RUNNER", callback_data="trex_start")]]
    
    await query.edit_message_text(
        "🦖 T-REX RUNNER!\n\n"
        "Dodge cacti and earn TON based on your score!\n"
        "• 0-100 points: 0.001 TON\n"
        "• 101-500 points: 0.005 TON\n"
        "• 501-1000 points: 0.01 TON\n"
        "• 1000+ points: 0.02 TON\n\n"
        "Play in the MiniApp for the best experience!",
        reply_markup=InlineKeyboardMarkup(keyboard))

async def edge_surf_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start Edge Surf game"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    
    # Check game cooldown
    last_played = user_data.get('last_played', {}).get('edge_surf')
    if last_played and (datetime.datetime.now() - last_played).seconds < Config.GAME_COOLDOWN * 60:
        cooldown = Config.GAME_COOLDOWN * 60 - (datetime.datetime.now() - last_played).seconds
        await query.edit_message_text(
            f"⏳ You can play Edge Surf again in {cooldown // 60} minutes!"
        )
        return
    
    keyboard = [[InlineKeyboardButton("🏄 PLAY EDGE SURF", callback_data="edge_surf_start")]]
    
    await query.edit_message_text(
        "🏄 EDGE SURF!\n\n"
        "Surf the edge and collect coins!\n"
        "• Each coin: 0.0001 TON\n"
        "• Bonus for high scores\n"
        "• Compete on leaderboards\n\n"
        "Play in the MiniApp for the best experience!",
        reply_markup=InlineKeyboardMarkup(keyboard))

# ================
# PREMIUM GAME HANDLERS
# ================

async def handle_premium_games_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle premium games selection"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    
    if not user_data.get('is_premium', False):
        keyboard = [
            [InlineKeyboardButton("Get Premium", callback_data="get_premium")],
            [InlineKeyboardButton("Free Games", callback_data="play")]
        ]
        
        await query.edit_message_text(
            "♟️ Premium Games require premium access!\n\n"
            "Upgrade to premium to unlock:\n"
            "• Higher earning potential\n"
            "• Exclusive game modes\n"
            "• Multiplayer competitions\n"
            "• Tournament prizes\n\n"
            "Get premium through the MiniApp or with Telegram Stars!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # Show premium games menu
    keyboard = [
        [InlineKeyboardButton("🕵️ Crypto Crew: Sabotage", callback_data="sabotage")],
        [InlineKeyboardButton("🎯 Mini Royal", callback_data="mini_royal")],
        [InlineKeyboardButton("♟️ Chess Masters", callback_data="chess")],
        [InlineKeyboardButton("🎱 Pool Game", callback_data="pool")],
        [InlineKeyboardButton("🃏 Poker Game", callback_data="poker")],
        [InlineKeyboardButton("⬅️ Back to Free Games", callback_data="play")]
    ]
    
    await query.edit_message_text(
        "♟️ <b>Premium Games</b>\n\n"
        "Choose from our exclusive premium games:\n\n"
        "• 🕵️ Crypto Crew: Sabotage - Social deduction game\n"
        "• 🎯 Mini Royal - Battle royale style game\n"
        "• ♟️ Chess Masters - Competitive chess\n"
        "• 🎱 Pool Game - 8-ball pool tournament\n"
        "• 🃏 Poker Game - Texas Hold'em poker\n\n"
        "Earn up to 10x more TON in premium games!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def handle_sabotage_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle sabotage game callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data == "sabotage":
        # Start new sabotage game
        keyboard = [
            [InlineKeyboardButton("Create Game", callback_data="sabotage_create")],
            [InlineKeyboardButton("Join Game", callback_data="sabotage_join")],
            [InlineKeyboardButton("Game Rules", callback_data="sabotage_rules")]
        ]
        
        await query.edit_message_text(
            "🕵️ Crypto Crew: Sabotage\n\n"
            "A social deduction game where miners try to complete tasks while saboteurs "
            "try to steal gold without getting caught!\n\n"
            "Create a game or join an existing one:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data == "sabotage_create":
        # Create new sabotage game
        game_id = f"sabotage_{user_id}_{int(datetime.datetime.now().timestamp())}"
        game = SabotageGame(game_id, str(user_id))
        
        # Save to database
        from src.database.mongo import save_sabotage_game
        save_sabotage_game(game.to_dict())
        
        keyboard = [
            [InlineKeyboardButton("Join Game", callback_data=f"sabotage_join_{game_id}")],
            [InlineKeyboardButton("Invite Players", callback_data=f"sabotage_invite_{game_id}")]
        ]
        
        await query.edit_message_text(
            f"🎮 Game Created!\n\n"
            f"Game ID: {game_id}\n"
            f"Waiting for players to join...\n\n"
            f"Share this game ID with friends to invite them!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith("sabotage_join_"):
        game_id = data.split('_')[2]
        # Join existing game logic
        pass
    
    elif data == "sabotage_rules":
        await query.edit_message_text(
            "📖 Crypto Crew: Sabotage Rules\n\n"
            "👥 Players: 6-12 players\n"
            "🎯 Objective: Miners complete tasks, Saboteurs steal gold\n"
            "⏰ Duration: 15-30 minutes\n\n"
            "Roles:\n"
            "• ⛏️ Miners (4-10): Complete tasks to earn gold\n"
            "• 🕵️ Saboteurs (2): Sabotage tasks and steal gold\n"
            "• 🔍 Detective (1): Investigate suspicious players\n\n"
            "Rewards:\n"
            "• Winning team: 0.05-0.2 TON per player\n"
            "• MVP: Bonus 0.05 TON\n"
            "• Detective bonus: Extra 0.03 TON"
        )

async def handle_chess_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle chess game callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data == "chess":
        # Start new chess game
        game = ChessGame()
        game_id = game.create_game(user_id)
        
        keyboard = [
            [InlineKeyboardButton("Quick Match", callback_data=f"chess_quick_{game_id}")],
            [InlineKeyboardButton("Invite Friend", callback_data=f"chess_invite_{game_id}")],
            [InlineKeyboardButton("Tournaments", callback_data="chess_tournaments")]
        ]
        
        await query.edit_message_text(
            "♟️ Chess Masters\n\n"
            "Play competitive chess against other players!\n"
            "• Win up to 5000 GC per game\n"
            "• ELO rating system\n"
            "• Tournament rewards\n\n"
            "Choose your game mode:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith("chess_quick_"):
        game_id = data.split('_')[2]
        # Quick match logic
        pass
    
    elif data == "chess_tournaments":
        # Show tournaments
        keyboard = [
            [InlineKeyboardButton("Daily Tournament", callback_data="chess_tournament_daily")],
            [InlineKeyboardButton("Weekly Championship", callback_data="chess_tournament_weekly")],
            [InlineKeyboardButton("Back to Chess", callback_data="chess")]
        ]
        
        await query.edit_message_text(
            "🏆 Chess Tournaments\n\n"
            "Join competitive tournaments with big prizes!\n\n"
            "Daily Tournament:\n"
            "• Entry: 100 GC\n"
            "• Prize pool: 1000 GC\n"
            "• Starts every day at 12:00 UTC\n\n"
            "Weekly Championship:\n"
            "• Entry: 500 GC\n"
            "• Prize pool: 5000 GC\n"
            "• Starts every Sunday at 15:00 UTC",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def handle_pool_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pool game callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data == "pool":
        keyboard = [
            [InlineKeyboardButton("Quick Match", callback_data="pool_quick")],
            [InlineKeyboardButton("Create Tournament", callback_data="pool_tournament")],
            [InlineKeyboardButton("Practice Mode", callback_data="pool_practice")]
        ]
        
        await query.edit_message_text(
            "🎱 Pool Masters\n\n"
            "Play 8-ball pool against other players!\n"
            "• Win up to 5000 GC per game\n"
            "• Tournament prizes\n"
            "• Practice mode available\n\n"
            "Choose your game mode:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data == "pool_quick":
        # Quick match logic
        game = PoolGame()
        game_id = game.create_quick_match(user_id)
        
        await query.edit_message_text(
            "🔍 Finding opponent...\n\n"
            "You'll be notified when a match is found!\n"
            "Estimated wait time: 1-3 minutes"
        )
    
    elif data == "pool_tournament":
        # Tournament creation
        keyboard = [
            [InlineKeyboardButton("8 Players (500 GC)", callback_data="pool_tourney_8")],
            [InlineKeyboardButton("16 Players (1000 GC)", callback_data="pool_tourney_16")],
            [InlineKeyboardButton("32 Players (2000 GC)", callback_data="pool_tourney_32")]
        ]
        
        await query.edit_message_text(
            "🏆 Create Tournament\n\n"
            "Choose tournament size and entry fee:\n\n"
            "8 Players Tournament:\n"
            "• Entry: 500 GC\n"
            "• Prize: 3000 GC (1st: 1500, 2nd: 1000, 3rd: 500)\n\n"
            "16 Players Tournament:\n"
            "• Entry: 1000 GC\n"
            "• Prize: 12000 GC (1st: 6000, 2nd: 4000, 3rd: 2000)\n\n"
            "32 Players Tournament:\n"
            "• Entry: 2000 GC\n"
            "• Prize: 48000 GC (1st: 24000, 2nd: 16000, 3rd: 8000)",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def handle_poker_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle poker game callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data == "poker":
        keyboard = [
            [InlineKeyboardButton("Join Table", callback_data="poker_join")],
            [InlineKeyboardButton("Create Table", callback_data="poker_create")],
            [InlineKeyboardButton("Tournaments", callback_data="poker_tournaments")]
        ]
        
        await query.edit_message_text(
            "🃏 Poker Royale\n\n"
            "Play Texas Hold'em poker with real stakes!\n"
            "• Win up to 10000 GC per game\n"
            "• Tournament series\n"
            "• Sit & Go tables\n\n"
            "Choose your game:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data == "poker_join":
        # Join poker table
        game = PokerGame()
        tables = game.get_available_tables()
        
        keyboard = []
        for table in tables[:5]:  # Show first 5 tables
            keyboard.append([
                InlineKeyboardButton(
                    f"Table {table['id']} - {table['stakes']} GC",
                    callback_data=f"poker_table_{table['id']}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("Refresh", callback_data="poker_join")])
        
        await query.edit_message_text(
            "🃏 Available Poker Tables\n\n"
            "Choose a table to join:\n"
            "• Small Stakes: 100-500 GC\n"
            "• Medium Stakes: 500-2000 GC\n"
            "• High Stakes: 2000-10000 GC\n\n"
            "Click refresh to see updated tables:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data == "poker_tournaments":
        # Show poker tournaments
        keyboard = [
            [InlineKeyboardButton("Daily Freeroll", callback_data="poker_tourney_daily")],
            [InlineKeyboardButton("Weekly Championship", callback_data="poker_tourney_weekly")],
            [InlineKeyboardButton("High Roller", callback_data="poker_tourney_high")]
        ]
        
        await query.edit_message_text(
            "🏆 Poker Tournaments\n\n"
            "Join exciting poker tournaments!\n\n"
            "Daily Freeroll:\n"
            "• Free entry\n"
            "• Prize pool: 1000 GC\n"
            "• Starts every 4 hours\n\n"
            "Weekly Championship:\n"
            "• Entry: 2000 GC\n"
            "• Prize pool: 50000 GC\n"
            "• Every Sunday at 18:00 UTC\n\n"
            "High Roller:\n"
            "• Entry: 10000 GC\n"
            "• Prize pool: 200000 GC\n"
            "• Every Saturday at 20:00 UTC",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def handle_mini_royal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle mini royal game callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data == "mini_royal":
        keyboard = [
            [InlineKeyboardButton("Solo Queue", callback_data="mini_royal_solo")],
            [InlineKeyboardButton("Squad Mode", callback_data="mini_royal_squad")],
            [InlineKeyboardButton("Custom Game", callback_data="mini_royal_custom")]
        ]
        
        await query.edit_message_text(
            "🎯 Mini Royal\n\n"
            "Battle royale style game with last-man-standing gameplay!\n"
            "• Win up to 8000 GC per game\n"
            "• Squad gameplay\n"
            "• Unique power-ups\n\n"
            "Choose your game mode:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data == "mini_royal_solo":
        # Solo queue
        game = MiniRoyalGame()
        game_id = game.join_solo_queue(user_id)
        
        await query.edit_message_text(
            "🔍 Finding solo match...\n\n"
            "You'll join a game with 99 other players!\n"
            "Estimated wait time: 2-5 minutes\n\n"
            "Prepare for battle! ⚔️"
        )
    
    elif data == "mini_royal_squad":
        # Squad mode
        keyboard = [
            [InlineKeyboardButton("Create Squad", callback_data="mini_royal_create_squad")],
            [InlineKeyboardButton("Join Squad", callback_data="mini_royal_join_squad")],
            [InlineKeyboardButton("Find Random Squad", callback_data="mini_royal_random_squad")]
        ]
        
        await query.edit_message_text(
            "👥 Squad Mode\n\n"
            "Team up with friends or find random teammates!\n"
            "• Squads of 4 players\n"
            "• Team coordination bonuses\n"
            "• Shared victory rewards\n\n"
            "Choose an option:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ================
# WITHDRAWAL HANDLERS
# ================

async def withdraw_ton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle TON withdrawal request"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    
    # Check if user has TON address set
    if not user_data.get('ton_address'):
        context.user_data['awaiting_ton'] = True
        await query.edit_message_text(
            "🌐 Please send your TON address in the following format:\n"
            "`EQAhF...` (standard TON wallet address)\n\n"
            "Or type /cancel to abort",
            parse_mode='Markdown'
        )
        return
    
    # Check balance
    balance = user_data.get('game_coins', 0)
    if balance < Config.MIN_WITHDRAWAL:
        await query.edit_message_text(
            f"❌ Minimum withdrawal: {Config.MIN_WITHDRAWAL} GC\n"
            f"Your balance: {balance:,} GC"
        )
        return
    
    # Process withdrawal
    ton_amount = game_coins_to_ton(balance)
    success = process_ton_withdrawal(user_id, user_data['ton_address'], ton_amount)
    
    if success:
        # Reset balance
        update_balance(user_id, -balance)
        
        await query.edit_message_text(
            f"✅ Withdrawal processed!\n"
            f"💎 Sent: {ton_amount:.6f} TON\n"
            f"📬 To: {user_data['ton_address'][:8]}...{user_data['ton_address'][-6:]}\n\n"
            f"Transaction should arrive within 15 minutes."
        )
    else:
        await query.edit_message_text(
            "❌ Withdrawal failed!\n"
            "Please try again later or contact support."
        )

async def withdraw_cash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle cash withdrawal request"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    
    # Check if user has payment method set
    has_payment_method = any([
        user_data.get('mpesa_number'),
        user_data.get('paypal_email'),
        user_data.get('bank_details')
    ])
    
    if not has_payment_method:
        context.user_data['awaiting_payment_method'] = True
        keyboard = [
            [InlineKeyboardButton("📱 M-Pesa", callback_data="set_mpesa")],
            [InlineKeyboardButton("💳 PayPal", callback_data="set_paypal")],
            [InlineKeyboardButton("🏦 Bank", callback_data="set_bank")]
        ]
        
        await query.edit_message_text(
            "💸 Please set up a payment method first:\n\n"
            "Choose your preferred withdrawal method:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # Show currency options
    keyboard = [
        [InlineKeyboardButton("💵 USD", callback_data="cash_usd")],
        [InlineKeyboardButton("💶 EUR", callback_data="cash_eur")],
        [InlineKeyboardButton("KES", callback_data="cash_kes")],
        [InlineKeyboardButton("💎 TON (Crypto)", callback_data="withdraw_ton")]
    ]
    
    await query.edit_message_text(
        "💱 Select currency for cash withdrawal:\n\n"
        "Conversion rates:\n"
        "• 1 TON ≈ $2.10 USD\n"
        "• 1 TON ≈ €1.95 EUR\n"
        "• 1 TON ≈ 300 KES\n\n"
        "Processing fee: 5%",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_cash_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process cash withdrawal selection"""
    query = update.callback_query
    await query.answer()
    
    currency = query.data.split('_')[1].upper()
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    
    balance = user_data.get('game_coins', 0)
    ton_amount = game_coins_to_ton(balance)
    
    # Convert to selected currency
    cash_amount = convert_currency(ton_amount, 'TON', currency)
    fee = calculate_fee(cash_amount, 0.05)  # 5% fee
    net_amount = cash_amount - fee
    
    # Process through OTC desk
    result = otc_desk.process_withdrawal(user_id, currency, net_amount)
    
    if result['success']:
        # Reset balance
        update_balance(user_id, -balance)
        
        await query.edit_message_text(
            f"✅ Cash withdrawal processed!\n\n"
            f"💸 Amount: {net_amount:.2f} {currency}\n"
            f"📋 Reference: {result['reference']}\n"
            f"⏰ ETA: 24-48 hours\n\n"
            f"You will receive a confirmation when processed."
        )
    else:
        await query.edit_message_text(
            f"❌ Withdrawal failed!\n"
            f"Error: {result.get('error', 'Unknown error')}\n\n"
            f"Please try again later or contact support."
        )

async def handle_clicker_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle clicker game callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data == "clicker":
        await clicker_game(update, context)
    elif data == "clicker_click":
        await clicker_click(update, context)

async def handle_trex_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle T-Rex game callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data == "trex":
        await trex_game(update, context)
    elif data == "trex_start":
        # Start T-Rex game in MiniApp
        miniapp_url = f"https://{Config.RENDER_URL}/miniapp?game=trex"
        keyboard = [[InlineKeyboardButton("🦖 Play T-Rex", url=miniapp_url)]]
        
        await query.edit_message_text(
            "🦖 T-REX RUNNER\n\n"
            "Click the button below to play in the MiniApp!\n"
            "Your score will automatically convert to TON rewards.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def handle_edge_surf_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Edge Surf game callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data == "edge_surf":
        await edge_surf_game(update, context)
    elif data == "edge_surf_start":
        # Start Edge Surf game in MiniApp
        miniapp_url = f"https://{Config.RENDER_URL}/miniapp?game=edge_surf"
        keyboard = [[InlineKeyboardButton("🏄 Play Edge Surf", url=miniapp_url)]]
        
        await query.edit_message_text(
            "🏄 EDGE SURF\n\n"
            "Click the button below to play in the MiniApp!\n"
            "Collect coins and earn TON rewards automatically.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )