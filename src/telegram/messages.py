WELCOME_MESSAGE = """
👋 Welcome to CryptoGameMiner, {name}!

🎮 Play games, complete quests, and watch ads to earn TON cryptocurrency.
💎 Withdraw to your TON wallet or convert to cash via our OTC desk.

💰 Current Balance: {balance:.6f} TON
"""

BALANCE_MESSAGE = """
💎 Your Balance
Total: {balance:.6f} TON
Available: {available:.6f} TON
Pending: {pending:.6f} TON

💸 Minimum Withdrawal: {min_withdrawal} TON
"""

WITHDRAWAL_OPTIONS = """
💰 How would you like to withdraw?

1. 💎 TON Wallet - Send directly to your TON address
2. 💵 Cash via OTC Desk - Convert to cash (USD/EUR/KES)
"""

OTC_QUOTE = """
🔒 Final Offer:
• Selling: {amount_ton:.6f} TON
• Rate: {rate} {currency}/TON
• Fee: {fee:.2f} {currency}
• You Receive: {total:.2f} {currency}
"""

WITHDRAWAL_SUCCESS = """
✅ Withdrawal Successful!
Amount: {amount:.6f} TON
Method: {method}
Transaction: {tx_link}
"""

OTC_SUCCESS = """
💸 Cash Withdrawal Processing!
Deal ID: {deal_id}
Amount: {amount_ton:.6f} TON → {currency}
You'll receive payment within 24 hours.
"""

GAME_REWARD = """
🎮 Game Completed!
Score: {score}
Duration: {duration}s
Reward: {reward:.6f} TON
New Balance: {new_balance:.6f} TON
"""