import time
import logging
import requests
from threading import Thread
from src.integrations.tonclient import ton_client
from config import config

logger = logging.getLogger(__name__)

class BalanceMonitor:
    def __init__(self):
        self.hot_wallet = config.TON_HOT_WALLET
        self.admin_wallet = config.TON_ADMIN_ADDRESS
        self.min_hot_balance = config.MIN_HOT_BALANCE  # 5 TON
        self.min_admin_balance = config.MIN_ADMIN_BALANCE  # 50 TON
        self.alert_interval = 3600  # 1 hour
        self.last_alert = 0
        
    def check_balances(self):
        """Check wallet balances and alert if low"""
        hot_balance = ton_client.get_balance(self.hot_wallet)
        admin_balance = ton_client.get_balance(self.admin_wallet)
        
        logger.info(f"Hot wallet balance: {hot_balance:.6f} TON")
        logger.info(f"Admin wallet balance: {admin_balance:.6f} TON")
        
        current_time = time.time()
        alerts = []
        
        if hot_balance < self.min_hot_balance:
            alerts.append(f"🚨 HOT WALLET LOW: {hot_balance:.6f} TON")
        
        if admin_balance < self.min_admin_balance:
            alerts.append(f"🚨 ADMIN WALLET LOW: {admin_balance:.6f} TON")
        
        if alerts and (current_time - self.last_alert) > self.alert_interval:
            self.send_alert("\n".join(alerts))
            self.last_alert = current_time
    
    def send_alert(self, message: str):
        """Send alert to admin"""
        if not config.ADMIN_ID:
            return
            
        try:
            # In a real implementation, send via Telegram bot
            # For now, we'll log it
            logger.warning(f"ALERT: {message}")
            
            # Example of sending to a webhook
            webhook_url = config.ALERT_WEBHOOK
            if webhook_url:
                requests.post(webhook_url, json={"text": message})
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
    
    def start_monitoring(self, interval=300):
        """Start background monitoring"""
        def monitor():
            while True:
                try:
                    self.check_balances()
                except Exception as e:
                    logger.error(f"Balance monitoring error: {e}")
                time.sleep(interval)
        
        Thread(target=monitor, daemon=True).start()

# Global monitor instance
balance_monitor = BalanceMonitor()