from telegram.ext import (
    CommandHandler, CallbackQueryHandler,
    Application
)
from . import commands, callbacks

def setup_handlers(application: Application):
    # Command handlers
    application.add_handler(CommandHandler("start", commands.start))
    application.add_handler(CommandHandler("play", commands.play_game))
    application.add_handler(CommandHandler("balance", commands.show_balance))
    application.add_handler(CommandHandler("withdraw", commands.withdraw))
    application.add_handler(CommandHandler("faucet", commands.faucet))
    application.add_handler(CommandHandler("app", commands.miniapp_command))
    application.add_handler(CommandHandler("leaderboard", commands.show_leaderboard))
    application.add_handler(CommandHandler("quests", commands.show_quests))
    application.add_handler(CommandHandler("set_withdrawal", commands.set_withdrawal))
    application.add_handler(CommandHandler("weekend", commands.weekend_promotion))

    # Game handlers
    application.add_handler(CallbackQueryHandler(callbacks.trivia_game, pattern='^trivia$'))
    application.add_handler(CallbackQueryHandler(callbacks.handle_trivia_answer, pattern='^trivia_'))
    application.add_handler(CallbackQueryHandler(callbacks.clicker_game, pattern='^clicker$'))
    application.add_handler(CallbackQueryHandler(callbacks.handle_click, pattern='^clicker_click$'))
    application.add_handler(CallbackQueryHandler(callbacks.finish_clicker, pattern='^clicker_finish$'))
    application.add_handler(CallbackQueryHandler(callbacks.spin_game, pattern='^spin$'))
    application.add_handler(CallbackQueryHandler(callbacks.spin_action, pattern='^spin_action$'))
    application.add_handler(CallbackQueryHandler(callbacks.daily_bonus, pattern='^daily$'))
    
    # Withdrawal handlers
    application.add_handler(CallbackQueryHandler(callbacks.process_withdrawal_selection, pattern='^withdraw_'))
    
    # Setup handlers
    application.add_handler(CallbackQueryHandler(callbacks.set_nano_address, pattern='^set_nano$'))
    application.add_handler(CallbackQueryHandler(callbacks.set_mpesa_number, pattern='^set_mpesa$'))
    application.add_handler(CallbackQueryHandler(callbacks.set_paypal_email, pattern='^set_paypal$'))
    
    # Quest handlers
    application.add_handler(CallbackQueryHandler(callbacks.quest_details, pattern='^quest_'))
    application.add_handler(CallbackQueryHandler(callbacks.complete_quest, pattern='^complete_'))
    application.add_handler(CallbackQueryHandler(callbacks.back_to_quests, pattern='^back_to_quests$'))
    
    # Navigation
    application.add_handler(CallbackQueryHandler(callbacks.back_to_main, pattern='^back_to_main$'))
    
    # Error handler
    application.add_error_handler(callbacks.error_handler)

    # In setup.py - Add new handlers
    application.add_handler(CallbackQueryHandler(callbacks.attach_menu_install, pattern='^attach_install_'))
    application.add_handler(CallbackQueryHandler(callbacks.attach_menu_remove, pattern='^attach_remove_'))
    application.add_handler(CallbackQueryHandler(callbacks.attach_menu_info, pattern='^attach_info_'))