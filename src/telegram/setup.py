from telegram.ext import (
    CommandHandler, CallbackQueryHandler,
    Application, MessageHandler, filters
)
from . import commands, callbacks
import logging

logger = logging.getLogger(__name__)

def setup_handlers(application: Application):
    # ==================== COMMAND HANDLERS ====================
    
    # Basic commands
    application.add_handler(CommandHandler("start", commands.start))
    application.add_handler(CommandHandler("help", commands.start))  # Reuse start for help
    application.add_handler(CommandHandler("balance", commands.show_balance))
    application.add_handler(CommandHandler("play", commands.play_game))
    application.add_handler(CommandHandler("premium", commands.premium_games))
    application.add_handler(CommandHandler("withdraw", commands.withdraw))
    application.add_handler(CommandHandler("faucet", commands.faucet))
    application.add_handler(CommandHandler("app", commands.miniapp_command))
    application.add_handler(CommandHandler("miniapp", commands.miniapp_command))
    application.add_handler(CommandHandler("leaderboard", commands.show_leaderboard))
    application.add_handler(CommandHandler("quests", commands.show_quests))
    application.add_handler(CommandHandler("set_withdrawal", commands.set_withdrawal))
    application.add_handler(CommandHandler("weekend", commands.weekend_promotion))
    application.add_handler(CommandHandler("otc", commands.otc_info))
    application.add_handler(CommandHandler("support", commands.support))
    application.add_handler(CommandHandler("settings", commands.set_withdrawal))  # Alias
    
    # Game-specific commands
    application.add_handler(CommandHandler("trivia", callbacks.trivia_game))
    application.add_handler(CommandHandler("spin", callbacks.spin_game))
    application.add_handler(CommandHandler("clicker", callbacks.clicker_game))
    application.add_handler(CommandHandler("trex", callbacks.trex_game))
    application.add_handler(CommandHandler("edgesurf", callbacks.edge_surf_game))
    application.add_handler(CommandHandler("sabotage", commands.sabotage))
    application.add_handler(CommandHandler("chess", commands.chess_game))
    application.add_handler(CommandHandler("pool", commands.pool_game))
    application.add_handler(CommandHandler("poker", commands.poker_game))
    application.add_handler(CommandHandler("miniroyal", commands.mini_royal))
    
    # Premium & payment commands
    application.add_handler(CommandHandler("getpremium", callbacks.handle_premium_games_selection))
    application.add_handler(CommandHandler("stars", callbacks.handle_stars_balance))
    application.add_handler(CommandHandler("buy", callbacks.handle_stars_purchase))
    application.add_handler(CommandHandler("subscriptions", callbacks.handle_stars_subscriptions))
    application.add_handler(CommandHandler("affiliate", callbacks.affiliate_program))
    application.add_handler(CommandHandler("gifts", commands.gifts))
    application.add_handler(CommandHandler("mygifts", commands.my_gifts))
    
    # Betting & tournament commands
    application.add_handler(CommandHandler("bet", callbacks.handle_betting))
    application.add_handler(CommandHandler("challenge", callbacks.handle_challenge))
    application.add_handler(CommandHandler("mybets", callbacks.handle_my_bets))
    application.add_handler(CommandHandler("tournaments", callbacks.handle_tournaments))
    application.add_handler(CommandHandler("stats", callbacks.handle_stats))
    application.add_handler(CommandHandler("profile", callbacks.handle_profile))
    
    # ==================== CALLBACK QUERY HANDLERS ====================
    
    # Free Games
    application.add_handler(CallbackQueryHandler(callbacks.trivia_game, pattern='^trivia$'))
    application.add_handler(CallbackQueryHandler(callbacks.handle_trivia_answer, pattern='^trivia_'))
    application.add_handler(CallbackQueryHandler(callbacks.spin_game, pattern='^spin$'))
    application.add_handler(CallbackQueryHandler(callbacks.spin_action, pattern='^spin_action$'))
    application.add_handler(CallbackQueryHandler(callbacks.clicker_game, pattern='^clicker$'))
    application.add_handler(CallbackQueryHandler(callbacks.clicker_click, pattern='^clicker_click$'))
    application.add_handler(CallbackQueryHandler(callbacks.trex_game, pattern='^trex$'))
    application.add_handler(CallbackQueryHandler(callbacks.edge_surf_game, pattern='^edge_surf$'))
    
    # Premium Games
    application.add_handler(CallbackQueryHandler(callbacks.handle_premium_games_selection, pattern='^premium_games$'))
    application.add_handler(CallbackQueryHandler(callbacks.handle_sabotage_callback, pattern='^sabotage'))
    application.add_handler(CallbackQueryHandler(callbacks.handle_chess_callback, pattern='^chess'))
    application.add_handler(CallbackQueryHandler(callbacks.handle_pool_callback, pattern='^pool'))
    application.add_handler(CallbackQueryHandler(callbacks.handle_poker_callback, pattern='^poker'))
    application.add_handler(CallbackQueryHandler(callbacks.handle_mini_royal_callback, pattern='^mini_royal'))
    
    # Withdrawal & Payment
    application.add_handler(CallbackQueryHandler(callbacks.process_withdrawal_selection, pattern='^withdraw_'))
    application.add_handler(CallbackQueryHandler(callbacks.withdraw_ton, pattern='^withdraw_ton$'))
    application.add_handler(CallbackQueryHandler(callbacks.withdraw_cash, pattern='^withdraw_cash$'))
    application.add_handler(CallbackQueryHandler(callbacks.handle_cash_withdrawal, pattern='^cash_'))
    application.add_handler(CallbackQueryHandler(callbacks.set_ton_address, pattern='^set_ton$'))
    application.add_handler(CallbackQueryHandler(callbacks.set_mpesa_number, pattern='^set_mpesa$'))
    application.add_handler(CallbackQueryHandler(callbacks.set_paypal_email, pattern='^set_paypal$'))
    application.add_handler(CallbackQueryHandler(callbacks.select_payment_method, pattern='^set_bank$'))
    
    # Stars & Payments
    application.add_handler(CallbackQueryHandler(callbacks.handle_stars_purchase, pattern='^buy_stars'))
    application.add_handler(CallbackQueryHandler(callbacks.process_stars_purchase, pattern='^stars_buy_'))
    application.add_handler(CallbackQueryHandler(callbacks.complete_stars_purchase, pattern='^stars_complete_purchase$'))
    application.add_handler(CallbackQueryHandler(callbacks.handle_stars_balance, pattern='^stars_balance$'))
    application.add_handler(CallbackQueryHandler(callbacks.handle_stars_subscriptions, pattern='^stars_subscriptions$'))
    
    # Quests & Daily
    application.add_handler(CallbackQueryHandler(callbacks.daily_bonus, pattern='^daily$'))
    application.add_handler(CallbackQueryHandler(callbacks.quest_details, pattern='^quest_'))
    application.add_handler(CallbackQueryHandler(callbacks.complete_quest, pattern='^complete_'))
    application.add_handler(CallbackQueryHandler(callbacks.back_to_quests, pattern='^back_to_quests$'))
    
    # Gifts & Giveaways
    application.add_handler(CallbackQueryHandler(callbacks.handle_giveaway_creation, pattern='^giveaway_create$'))
    application.add_handler(CallbackQueryHandler(callbacks.handle_premium_giveaway, pattern='^giveaway_premium$'))
    application.add_handler(CallbackQueryHandler(callbacks.handle_stars_giveaway, pattern='^giveaway_stars$'))
    application.add_handler(CallbackQueryHandler(callbacks.handle_gift_sending, pattern='^gift_send_'))
    application.add_handler(CallbackQueryHandler(callbacks.handle_gift_view, pattern='^gift_view_'))
    application.add_handler(CallbackQueryHandler(callbacks.handle_gift_save, pattern='^gift_save_'))
    application.add_handler(CallbackQueryHandler(callbacks.handle_gift_convert, pattern='^gift_convert_'))
    
    # Affiliate & Referrals
    application.add_handler(CallbackQueryHandler(callbacks.affiliate_program, pattern='^affiliate_program$'))
    application.add_handler(CallbackQueryHandler(callbacks.join_affiliate, pattern='^affiliate_join$'))
    application.add_handler(CallbackQueryHandler(callbacks.affiliate_stats, pattern='^affiliate_stats$'))
    application.add_handler(CallbackQueryHandler(callbacks.affiliate_copy_link, pattern='^affiliate_copy_link$'))
    
    # Betting & Challenges
    application.add_handler(CallbackQueryHandler(callbacks.handle_betting, pattern='^bet_'))
    application.add_handler(CallbackQueryHandler(callbacks.handle_challenge, pattern='^challenge_'))
    application.add_handler(CallbackQueryHandler(callbacks.handle_my_bets, pattern='^mybets$'))
    application.add_handler(CallbackQueryHandler(callbacks.accept_challenge, pattern='^accept_'))
    application.add_handler(CallbackQueryHandler(callbacks.decline_challenge, pattern='^decline_'))
    
    # Tournaments
    application.add_handler(CallbackQueryHandler(callbacks.handle_tournaments, pattern='^tournaments$'))
    application.add_handler(CallbackQueryHandler(callbacks.join_tournament, pattern='^tournament_join_'))
    application.add_handler(CallbackQueryHandler(callbacks.create_tournament, pattern='^tournament_create_'))
    
    # Navigation
    application.add_handler(CallbackQueryHandler(callbacks.back_to_main, pattern='^back_to_main$'))
    application.add_handler(CallbackQueryHandler(callbacks.back_to_games, pattern='^back_to_games$'))
    application.add_handler(CallbackQueryHandler(callbacks.back_to_premium, pattern='^back_to_premium$'))
    
    # Attachment Menu
    application.add_handler(CallbackQueryHandler(callbacks.handle_attach_menu_install, pattern='^attach_install_'))
    application.add_handler(CallbackQueryHandler(callbacks.handle_attach_menu_remove, pattern='^attach_remove_'))
    application.add_handler(CallbackQueryHandler(callbacks.handle_attach_menu_info, pattern='^attach_info_'))
    application.add_handler(CallbackQueryHandler(callbacks.install_attach_menu, pattern='^attach_accept_'))
    application.add_handler(CallbackQueryHandler(callbacks.dismiss_suggestion, pattern='^suggestion_'))
    
    # Suggestions
    application.add_handler(CallbackQueryHandler(callbacks.show_suggestions, pattern='^show_suggestions$'))
    application.add_handler(CallbackQueryHandler(callbacks.dismiss_suggestion, pattern='^dismiss_'))
    
    # ==================== MESSAGE HANDLERS ====================
    
    # Handle payment method details input
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        callbacks.save_payment_details
    ))
    
    # Handle TON address input
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        callbacks.complete_ton_withdrawal
    ))
    
    # ==================== ERROR HANDLER ====================
    application.add_error_handler(callbacks.error_handler)
    
    logger.info("All handlers setup successfully")

# Additional setup function for webhook
def setup_webhook(application, webhook_url, secret_token):
    """Set up webhook for production"""
    try:
        application.run_webhook(
            listen="0.0.0.0",
            port=5000,
            url_path="webhook",
            webhook_url=webhook_url,
            secret_token=secret_token
        )
        logger.info(f"Webhook setup successfully at {webhook_url}")
        return True
    except Exception as e:
        logger.error(f"Webhook setup failed: {str(e)}")
        return False

# Polling setup for development
def setup_polling(application):
    """Set up polling for development"""
    try:
        application.run_polling()
        logger.info("Polling setup successfully")
        return True
    except Exception as e:
        logger.error(f"Polling setup failed: {str(e)}")
        return False