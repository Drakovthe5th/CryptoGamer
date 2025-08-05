from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 Play Games", callback_data="play")],
        [InlineKeyboardButton("💰 Withdraw", callback_data="withdraw")],
        [InlineKeyboardButton("🎯 Quests", callback_data="quests")],
        [InlineKeyboardButton("📊 Leaderboard", callback_data="leaderboard")]
    ])

def game_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧠 Trivia", callback_data="trivia")],
        [InlineKeyboardButton("🎰 Spin Wheel", callback_data="spin")],
        [InlineKeyboardButton("💥 Clicker", callback_data="clicker")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ])

def withdrawal_options():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 TON Wallet", callback_data="withdraw_ton")],
        [InlineKeyboardButton("💵 Cash via OTC", callback_data="withdraw_cash")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ])

def currency_options():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("USD", callback_data="cash_usd")],
        [InlineKeyboardButton("EUR", callback_data="cash_eur")],
        [InlineKeyboardButton("KES", callback_data="cash_kes")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ])

def payment_methods():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("M-Pesa", callback_data="paymethod_M-Pesa")],
        [InlineKeyboardButton("PayPal", callback_data="paymethod_PayPal")],
        [InlineKeyboardButton("Bank Transfer", callback_data="paymethod_Bank Transfer")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ])