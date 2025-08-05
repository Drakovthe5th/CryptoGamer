import os
import time
import logging
from datetime import datetime, timedelta
from src.database.firebase import db
from src.integrations.tonclient import ton_client
from src.integrations.mpesa import send_mpesa_payment
from src.integrations.paypal import create_payout
from src.utils import maintenance
from src.utils.maintenance import is_maintenance_mode
from config import config

logger = logging.getLogger(__name__)

class WithdrawalProcessor:
    def __init__(self):
        self.last_processed = datetime.min
        self.daily_withdrawal_limit = config.DAILY_WITHDRAWAL_LIMIT
        self.user_daily_limit = config.USER_DAILY_WITHDRAWAL_LIMIT
        self.today_withdrawn = 0.0
        self.load_daily_total()

    def load_daily_total(self):
        """Load today's withdrawal total from DB"""
        today = datetime.now().strftime("%Y-%m-%d")
        doc_ref = db.collection("system_stats").document("withdrawals")
        doc = doc_ref.get()
        
        if doc.exists:
            data = doc.to_dict()
            if data.get("date") == today:
                self.today_withdrawn = data.get("total", 0.0)

    def update_daily_total(self, amount: float):
        """Update daily withdrawal total in DB"""
        today = datetime.now().strftime("%Y-%m-%d")
        doc_ref = db.collection("system_stats").document("withdrawals")
        
        if doc_ref.get().exists and doc_ref.get().to_dict().get("date") == today:
            doc_ref.update({"total": self.today_withdrawn})
        else:
            doc_ref.set({
                "date": today,
                "total": amount
            })
        self.today_withdrawn = amount

    def process_withdrawal(self, user_id: str, method: str, amount: float, details: dict) -> dict:
        """Process a withdrawal request"""
        # Check maintenance mode
        if is_maintenance_mode():
            return {"success": False, "error": "Withdrawals temporarily disabled for maintenance"}
        
        # Check system limits
        if self.today_withdrawn + amount > self.daily_withdrawal_limit:
            return {"success": False, "error": "Daily withdrawal limit reached"}
        
        # Check user limits
        user_ref = db.collection("users").document(str(user_id))
        user_data = user_ref.get().to_dict()
        
        # Reset daily limit if new day
        user_today = datetime.now().strftime("%Y-%m-%d")
        if user_data.get("last_withdrawal_date") != user_today:
            user_ref.update({
                "last_withdrawal_date": user_today,
                "today_withdrawn": 0.0
            })
            user_data["today_withdrawn"] = 0.0
        
        # Check user limit
        if user_data.get("today_withdrawn", 0.0) + amount > self.user_daily_limit:
            return {"success": False, "error": "You've reached your daily withdrawal limit"}
        
        # Process based on method
        result = None
        if method == "ton":
            result = self.process_ton_withdrawal(user_id, amount, details)
        elif method == "mpesa":
            result = self.process_mpesa_withdrawal(user_id, amount, details)
        elif method == "paypal":
            result = self.process_paypal_withdrawal(user_id, amount, details)
        
        # Update limits if successful
        if result and result.get("success"):
            # Update system total
            self.today_withdrawn += amount
            self.update_daily_total(self.today_withdrawn)
            
            # Update user total
            user_ref.update({
                "today_withdrawn": user_data.get("today_withdrawn", 0.0) + amount,
                "total_withdrawn": user_data.get("total_withdrawn", 0.0) + amount
            })
        
        return result

    def process_ton_withdrawal(self, user_id: str, amount: float, details: dict) -> dict:
        """Process TON blockchain withdrawal"""
        to_address = details.get("address")
        if not to_address:
            return {"success": False, "error": "Missing wallet address"}
        
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
            
            return {
                "success": True,
                "tx_hash": result["tx_hash"],
                "explorer_url": result["explorer_url"]
            }
        return {"success": False, "error": "Transaction failed"}

    def process_mpesa_withdrawal(self, user_id: str, amount: float, details: dict) -> dict:
        """Process M-Pesa withdrawal"""
        phone = details.get("phone")
        if not phone:
            return {"success": False, "error": "Missing phone number"}
        
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
            
            return {"success": True, "amount_kes": amount_kes}
        return {"success": False, "error": result.get("error", "MPesa payment failed")}

    def process_paypal_withdrawal(self, user_id: str, amount: float, details: dict) -> dict:
        """Process PayPal withdrawal"""
        email = details.get("email")
        if not email:
            return {"success": False, "error": "Missing email address"}
        
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
            
            return {"success": True, "amount_usd": amount_usd}
        return {"success": False, "error": result.get("error", "PayPal payout failed")}

# Global processor instance
withdrawal_processor = WithdrawalProcessor()