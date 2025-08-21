import os
import time
import logging
import threading
from datetime import datetime, timedelta
from src.database.mongo import db, update_game_coins, get_user_data
from src.integrations.tonclient import ton_client
from src.integrations.mpesa import send_mpesa_payment
from src.integrations.paypal import create_payout
from src.utils import maintenance
from src.utils.maintenance import any_issues_found as is_maintenance_mode
from config import config

logger = logging.getLogger(__name__)
MIN_WITHDRAWAL = config.MIN_WITHDRAWAL_GC  # GC
TON_TO_GC_RATE = config.GC_TO_TON_RATE

class WithdrawalProcessor:
    def __init__(self):
        self.last_processed = datetime.min
        self.daily_withdrawal_limit = config.DAILY_WITHDRAWAL_LIMIT
        self.user_daily_limit = config.USER_DAILY_WITHDRAWAL_LIMIT
        self.today_withdrawn = 0.0
        self.load_daily_total()

    def load_daily_total(self):
        today = datetime.utcnow().strftime("%Y-%m-%d")
        doc = db.system_stats.find_one({"name": "withdrawals", "date": today})
        if doc:
            self.today_withdrawn = doc.get("total", 0.0)

    def update_daily_total(self, amount: float):
        today = datetime.utcnow().strftime("%Y-%m-%d")
        db.system_stats.update_one(
            {"name": "withdrawals", "date": today},
            {"$set": {"total": amount}},
            upsert=True
        )
        self.today_withdrawn = amount
    
    def check_gameplay_time(self, user_id):
        """Check if user has the minimum required gameplay time"""
        user = get_user_data(user_id)
        total_gameplay_hours = user.get('total_gameplay_hours', 0)
        return total_gameplay_hours >= config.MIN_GAMEPLAY_HOURS

    def check_withdrawal_eligibility(self, user_id):
        """Check if user meets all withdrawal requirements"""
        # Check participation score (75% requirement)
        user = get_user_data(user_id)
        max_possible_score = 100  # This should be calculated based on available activities
        current_score = user.get('participation_score', 0)
        participation_ok = (current_score / max_possible_score) >= 0.75
        
        # Check gameplay time (500 hours requirement)
        gameplay_ok = self.check_gameplay_time(user_id)
        
        # Check minimum balance
        balance_ok = user.get('game_coins', 0) >= MIN_WITHDRAWAL
        
        return {
            'eligible': participation_ok and gameplay_ok and balance_ok,
            'reasons': [
                'Insufficient participation score' if not participation_ok else None,
                f'Insufficient gameplay time (need {config.MIN_GAMEPLAY_HOURS} hours)' if not gameplay_ok else None,
                'Insufficient balance' if not balance_ok else None
            ]
        }

    def process_withdrawal(self, user_id):
        """Process GC withdrawal to TON"""
        # Check eligibility first
        eligibility = self.check_withdrawal_eligibility(user_id)
        if not eligibility['eligible']:
            reasons = [r for r in eligibility['reasons'] if r is not None]
            raise Exception(f"Withdrawal not allowed: {', '.join(reasons)}")
        
        user = get_user_data(user_id)
        
        if not user.wallet_address:
            raise Exception("Wallet not connected")
        
        if user.game_coins < MIN_WITHDRAWAL:
            raise Exception("Insufficient balance")
        
        # Check daily limits
        if self.today_withdrawn >= self.daily_withdrawal_limit:
            raise Exception("Daily withdrawal limit reached")
        
        # Convert to TON
        ton_amount = user.game_coins / TON_TO_GC_RATE
        
        # Send transaction
        tx_hash = ton_client.send_ton(user.wallet_address, ton_amount)
        
        # Update user balance
        success, new_balance = update_game_coins(user_id, -MIN_WITHDRAWAL)
        if not success:
            raise Exception("Failed to update balance")
        
        # Update daily total
        self.update_daily_total(self.today_withdrawn + ton_amount)
        
        return tx_hash

    def process_ton_withdrawal(self, user_id: str, amount: float, details: dict) -> dict:
        """Process TON blockchain withdrawal"""
        # Check eligibility first
        eligibility = self.check_withdrawal_eligibility(user_id)
        if not eligibility['eligible']:
            reasons = [r for r in eligibility['reasons'] if r is not None]
            return {"success": False, "error": f"Withdrawal not allowed: {', '.join(reasons)}"}
            
        to_address = details.get("address")
        if not to_address:
            return {"success": False, "error": "Missing wallet address"}
        
        # Check daily limits
        if self.today_withdrawn + amount > self.daily_withdrawal_limit:
            return {"success": False, "error": "Daily withdrawal limit exceeded"}
        
        # Get private key (in production, use secure storage)
        private_key = os.getenv("TON_SIGNING_KEY")
        if not private_key:
            return {"success": False, "error": "System configuration error"}
        
        # Send transaction
        result = ton_client.send_transaction(
            from_address=config.TON_HOT_WALLET,
            to_address=to_address,
            amount=amount,
            private_key=private_key
        )
        
        if result:
            # Save withdrawal record
            withdrawal_data = {
                "user_id": user_id,
                "amount": amount,
                "method": "ton",
                "address": to_address,
                "tx_hash": result["tx_hash"],
                "status": "completed",
                "timestamp": datetime.now()
            }
            db.collection("withdrawals").add(withdrawal_data)
            
            # Update daily total
            self.update_daily_total(self.today_withdrawn + amount)
            
            return {
                "success": True,
                "tx_hash": result["tx_hash"],
                "explorer_url": result["explorer_url"]
            }
        return {"success": False, "error": "Transaction failed"}

    def process_mpesa_withdrawal(self, user_id: str, amount: float, details: dict) -> dict:
        """Process M-Pesa withdrawal"""
        # Check eligibility first
        eligibility = self.check_withdrawal_eligibility(user_id)
        if not eligibility['eligible']:
            reasons = [r for r in eligibility['reasons'] if r is not None]
            return {"success": False, "error": f"Withdrawal not allowed: {', '.join(reasons)}"}
            
        phone = details.get("phone")
        if not phone:
            return {"success": False, "error": "Missing phone number"}
        
        # Check daily limits
        if self.today_withdrawn + amount > self.daily_withdrawal_limit:
            return {"success": False, "error": "Daily withdrawal limit exceeded"}
        
        # Get conversion rate
        rate = config.OTC_RATES.get("KES", 700.0)
        amount_kes = amount * rate
        
        # Send payment
        result = send_mpesa_payment(phone, amount_kes, "KES")
        
        if result and result.get("status") == "success":
            # Save withdrawal record
            withdrawal_data = {
                "user_id": user_id,
                "amount": amount,
                "method": "mpesa",
                "phone": phone,
                "amount_kes": amount_kes,
                "status": "completed",
                "timestamp": datetime.now()
            }
            db.collection("withdrawals").add(withdrawal_data)
            
            # Update daily total
            self.update_daily_total(self.today_withdrawn + amount)
            
            return {"success": True, "amount_kes": amount_kes}
        return {"success": False, "error": result.get("error", "MPesa payment failed")}

    def process_paypal_withdrawal(self, user_id: str, amount: float, details: dict) -> dict:
        """Process PayPal withdrawal"""
        # Check eligibility first
        eligibility = self.check_withdrawal_eligibility(user_id)
        if not eligibility['eligible']:
            reasons = [r for r in eligibility['reasons'] if r is not None]
            return {"success": False, "error": f"Withdrawal not allowed: {', '.join(reasons)}"}
            
        email = details.get("email")
        if not email:
            return {"success": False, "error": "Missing email address"}
        
        # Check daily limits
        if self.today_withdrawn + amount > self.daily_withdrawal_limit:
            return {"success": False, "error": "Daily withdrawal limit exceeded"}
        
        # Get conversion rate
        rate = config.OTC_RATES.get("USD", 5.0)
        amount_usd = amount * rate
        
        # Send payment
        result = create_payout(email, amount_usd, "USD")
        
        if result and result.get("success"):
            # Save withdrawal record
            withdrawal_data = {
                "user_id": user_id,
                "amount": amount,
                "method": "paypal",
                "email": email,
                "amount_usd": amount_usd,
                "status": "completed",
                "timestamp": datetime.now()
            }
            db.collection("withdrawals").add(withdrawal_data)
            
            # Update daily total
            self.update_daily_total(self.today_withdrawn + amount)
            
            return {"success": True, "amount_usd": amount_usd}
        return {"success": False, "error": result.get("error", "PayPal payout failed")}

    def get_gameplay_time(self, user_id):
        """Get user's total gameplay time in hours"""
        user = get_user_data(user_id)
        return user.get('total_gameplay_hours', 0)

# Global processor instance
withdrawal_processor = None

def get_withdrawal_processor():
    if config.TON_ENABLED:
        return WithdrawalProcessor()
    else:
        return DummyWithdrawalProcessor()
        
class DummyWithdrawalProcessor:
    def process_gc_withdrawal(self, user_id):
        return False, "Withdrawals temporarily unavailable"
    
def start_withdrawal_processor():
    """Start the withdrawal processor as a background service"""
    logger.info("🚀 Starting withdrawal processor")
    processor = WithdrawalProcessor()
    processor_thread = threading.Thread(target=processor.run, daemon=True)
    processor_thread.start()
    return processor