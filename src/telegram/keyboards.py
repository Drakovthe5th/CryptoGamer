from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 Play Games", callback_data="play")],
        [InlineKeyboardButton("💰 Withdraw", callback_data="withdraw")],
        [InlineKeyboardButton("🎯 Quests", callback_data="quests")]
    ])

def game_selection_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧠 Trivia Quiz", callback_data="trivia")],
        [InlineKeyboardButton("💥 Clicker Game", callback_data="clicker")],
        [InlineKeyboardButton("🎰 Spin Wheel", callback_data="spin")],
        [InlineKeyboardButton("🎁 Daily Bonus", callback_data="daily")]
    ])

def withdrawal_methods_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Nano", callback_data="withdraw_nano")],
        [InlineKeyboardButton("📱 M-Pesa", callback_data="withdraw_mpesa")],
        [InlineKeyboardButton("💳 PayPal", callback_data="withdraw_paypal")],
        [InlineKeyboardButton("❌ Cancel", callback_data="withdraw_cancel")]
    ])

def setup_withdrawal_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Set Nano Address", callback_data="set_nano")],
        [InlineKeyboardButton("📱 Set M-Pesa Number", callback_data="set_mpesa")],
        [InlineKeyboardButton("💳 Set PayPal Email", callback_data="set_paypal")]
    ])

def back_to_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")]
    ])