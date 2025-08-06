import logging
import os
import time
import psutil
import requests
from config import config
from src.integrations.telegram import send_telegram_message

logger = logging.getLogger(__name__)

def check_server_load() -> bool:
    """Check current server load"""
    try:
        # Get system load averages
        load1, load5, load15 = os.getloadavg()
        cpu_percent = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        
        logger.info(f"Server load: {load1:.2f}, {load5:.2f}, {load5:.2f} | CPU: {cpu_percent}% | Mem: {mem.percent}%")
        
        # Thresholds for alerting
        if load1 > 5.0 or cpu_percent > 90 or mem.percent > 90:
            send_alert_to_admin("⚠️ High server load detected")
            return True
        return False
    except Exception as e:
        logger.error(f"Server load check failed: {e}")
        return True

def check_ton_node() -> bool:
    """Check TON node connectivity"""
    try:
        from src.integrations.ton import ton_wallet
        start = time.time()
        # Perform a simple balance check
        balance = asyncio.run(ton_wallet.get_balance(force_update=True))
        latency = time.time() - start
        
        logger.info(f"TON node is reachable | Balance: {balance} TON | Latency: {latency:.2f}s")
        
        if latency > 5.0 or balance <= 0:
            send_alert_to_admin("⚠️ TON node issue detected")
            return False
        return True
    except Exception as e:
        logger.error(f"TON node check failed: {e}")
        send_alert_to_admin("🔥 TON node unreachable")
        return False

def check_payment_gateways() -> bool:
    """Check payment gateway status"""
    try:
        # Check M-PESA
        from src.integrations.mpesa import get_mpesa_token
        token = get_mpesa_token()
        mpesa_ok = token is not None
        
        # Check PayPal (stub implementation)
        paypal_ok = True
        
        logger.info(f"Payment gateways: M-PESA {'OK' if mpesa_ok else 'DOWN'}, PayPal {'OK' if paypal_ok else 'DOWN'}")
        
        if not mpesa_ok:
            send_alert_to_admin("⚠️ M-PESA gateway down")
        if not paypal_ok:
            send_alert_to_admin("⚠️ PayPal gateway down")
            
        return mpesa_ok and paypal_ok
    except Exception as e:
        logger.error(f"Payment gateway check failed: {e}")
        return False

def any_issues_found() -> bool:
    """Aggregate all checks"""
    server_issue = check_server_load()
    ton_issue = not check_ton_node()
    payment_issue = not check_payment_gateways()
    
    return server_issue or ton_issue or payment_issue

def send_alert_to_admin(message: str):
    """Send alert to admin via Telegram"""
    if config.ADMIN_USER_ID:
        send_telegram_message(config.ADMIN_USER_ID, message)
    logger.warning(message)