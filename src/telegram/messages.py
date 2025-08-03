def welcome_message(user):
    return (
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

def balance_message(balance, min_withdrawal):
    return (
        f"💰 Your Balance: {balance:.6f} XNO\n\n"
        f"💸 Minimum withdrawal: {min_withdrawal} XNO\n"
        "💳 Set up withdrawal methods with /set_withdrawal"
    )

def faucet_claimed_message(reward, new_balance):
    return (
        f"💧 You claimed {reward:.6f} XNO!\n"
        f"💰 New balance: {new_balance:.6f} XNO"
    )

def withdrawal_options_message(balance, min_withdrawal):
    if balance < min_withdrawal:
        return (
            f"❌ Minimum withdrawal: {min_withdrawal} XNO\n"
            f"Your balance: {balance:.6f} XNO"
        )
    return "💸 Select withdrawal method:"

def miniapp_message():
    return (
        "📲 Open the CryptoGameBot MiniApp for a better gaming experience!\n\n"
        "👉 [Launch MiniApp](https://yourdomain.com/miniapp)\n\n"
        "Play games, check balance, and withdraw directly in-app!"
    )

def leaderboard_message(leaderboard, user_rank):
    text = "🏆 <b>TOP PLAYERS</b>\n\n"
    for idx, user in enumerate(leaderboard, start=1):
        text += f"{idx}. {user.get('username', 'Anonymous')} - {user.get('points', 0)} pts\n"
    text += f"\n👤 Your position: #{user_rank}"
    return text