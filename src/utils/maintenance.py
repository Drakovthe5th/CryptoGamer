import logging
import os
import time
import asyncio
import requests
from config import config
from src.integrations.telegram import send_telegram_message

# Try to import psutil with graceful fallback
try:
    import psutil
    PSUTIL_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("psutil imported successfully")
except ImportError as e:
    PSUTIL_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning(f"psutil not available: {e}. Using fallback system monitoring.")

def check_server_load() -> bool:
    """Check current server load"""
    try:
        if PSUTIL_AVAILABLE:
            # Full system monitoring with psutil
            load1, load5, load15 = os.getloadavg()
            cpu_percent = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory()
            
            logger.info(f"Server load: {load1:.2f}, {load5:.2f}, {load15:.2f} | CPU: {cpu_percent}% | Mem: {mem.percent}%")
            
            # Thresholds for alerting
            if load1 > 5.0 or cpu_percent > 90 or mem.percent > 90:
                send_alert_to_admin("⚠️ High server load detected")
                return True
            return False
        else:
            # Fallback monitoring without psutil
            try:
                # Try to get load average (Unix-like systems)
                load1, load5, load15 = os.getloadavg()
                logger.info(f"Server load (basic): {load1:.2f}, {load5:.2f}, {load15:.2f}")
                
                if load1 > 5.0:
                    send_alert_to_admin("⚠️ High server load detected (basic monitoring)")
                    return True
                return False
            except (AttributeError, OSError):
                # os.getloadavg() not available on Windows
                logger.info("Basic system monitoring active (limited metrics available)")
                return False
                
    except Exception as e:
        logger.error(f"Server load check failed: {e}")
        return True

def check_ton_node() -> bool:
    """Check TON node connectivity"""
    try:
        from src.integrations.ton import ton_wallet
        
        # Check if wallet is initialized
        if not ton_wallet.initialized:
            logger.warning("TON wallet not initialized, attempting to initialize...")
            success = asyncio.run(ton_wallet.initialize())
            if not success:
                send_alert_to_admin("🔥 TON wallet initialization failed")
                return False
        
        # Perform health check
        start = time.time()
        is_healthy = asyncio.run(ton_wallet.health_check())
        latency = time.time() - start
        
        if is_healthy:
            logger.info(f"TON node is reachable | Latency: {latency:.2f}s")
            
            # Optionally get balance (but don't fail if it errors)
            try:
                balance = asyncio.run(ton_wallet.get_balance())
                logger.info(f"TON wallet balance: {balance:.6f} TON")
            except Exception as e:
                logger.warning(f"Could not fetch balance: {e}")
            
            if latency > 10.0:  # Increased threshold for slower connections
                send_alert_to_admin("⚠️ TON node slow response time")
                return False
            return True
        else:
            send_alert_to_admin("🔥 TON node health check failed")
            return False
            
    except Exception as e:
        logger.error(f"TON node check failed: {e}")
        send_alert_to_admin(f"🔥 TON node check error: {str(e)}")
        return False

def check_payment_gateways() -> bool:
    """Check payment gateway status"""
    try:
        mpesa_ok = True
        paypal_ok = True
        
        # Check M-PESA if enabled
        if hasattr(config, 'MPESA_ENABLED') and config.MPESA_ENABLED:
            try:
                from src.integrations.mpesa import get_mpesa_token
                token = get_mpesa_token()
                mpesa_ok = token is not None
            except ImportError:
                logger.info("M-PESA integration not available")
                mpesa_ok = True  # Don't fail if not implemented
            except Exception as e:
                logger.error(f"M-PESA check failed: {e}")
                mpesa_ok = False
        
        # Check PayPal if enabled
        if hasattr(config, 'PAYPAL_ENABLED') and config.PAYPAL_ENABLED:
            try:
                # Basic connectivity check to PayPal API
                response = requests.get(
                    "https://api.paypal.com/v1/oauth2/token",
                    timeout=10,
                    headers={'Accept': 'application/json'}
                )
                paypal_ok = response.status_code in [200, 401]  # 401 is expected without auth
            except Exception as e:
                logger.error(f"PayPal connectivity check failed: {e}")
                paypal_ok = False
        
        logger.info(f"Payment gateways: M-PESA {'OK' if mpesa_ok else 'DOWN'}, PayPal {'OK' if paypal_ok else 'DOWN'}")
        
        if not mpesa_ok:
            send_alert_to_admin("⚠️ M-PESA gateway issue")
        if not paypal_ok:
            send_alert_to_admin("⚠️ PayPal gateway issue")
            
        return mpesa_ok and paypal_ok
        
    except Exception as e:
        logger.error(f"Payment gateway check failed: {e}")
        return True  # Don't fail the overall health check for payment gateway issues

def check_database_connectivity() -> bool:
    """Check Firebase database connectivity"""
    try:
        from src.database.firebase import db
        
        # Simple connectivity test
        test_result = db.collection('health_check').limit(1).get()
        logger.info("Firebase database connectivity: OK")
        return True
        
    except Exception as e:
        logger.error(f"Database connectivity check failed: {e}")
        send_alert_to_admin(f"🔥 Database connectivity issue: {str(e)}")
        return False

def any_issues_found() -> bool:
    """Aggregate all checks"""
    issues = []
    
    try:
        # Server load check
        server_issue = check_server_load()
        if server_issue:
            issues.append("server_load")
    except Exception as e:
        logger.error(f"Server load check error: {e}")
        issues.append("server_load_error")
    
    try:
        # TON node check
        ton_issue = not check_ton_node()
        if ton_issue:
            issues.append("ton_node")
    except Exception as e:
        logger.error(f"TON node check error: {e}")
        issues.append("ton_node_error")
    
    try:
        # Payment gateway check
        payment_issue = not check_payment_gateways()
        if payment_issue:
            issues.append("payment_gateways")
    except Exception as e:
        logger.error(f"Payment gateway check error: {e}")
        issues.append("payment_gateway_error")
    
    try:
        # Database connectivity check
        db_issue = not check_database_connectivity()
        if db_issue:
            issues.append("database")
    except Exception as e:
        logger.error(f"Database check error: {e}")
        issues.append("database_error")
    
    if issues:
        logger.warning(f"Health check issues found: {', '.join(issues)}")
        return True
    
    logger.info("All health checks passed")
    return False

def send_alert_to_admin(message: str):
    """Send alert to admin via Telegram"""
    try:
        if hasattr(config, 'ADMIN_USER_ID') and config.ADMIN_USER_ID:
            send_telegram_message(config.ADMIN_USER_ID, message)
        logger.warning(f"ALERT: {message}")
    except Exception as e:
        logger.error(f"Failed to send alert: {e}")

def get_system_info() -> dict:
    """Get comprehensive system information"""
    info = {
        "timestamp": time.time(),
        "psutil_available": PSUTIL_AVAILABLE
    }
    
    try:
        if PSUTIL_AVAILABLE:
            # Detailed system info with psutil
            info.update({
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory": {
                    "total": psutil.virtual_memory().total,
                    "available": psutil.virtual_memory().available,
                    "percent": psutil.virtual_memory().percent
                },
                "disk": {
                    "total": psutil.disk_usage('/').total,
                    "free": psutil.disk_usage('/').free,
                    "percent": psutil.disk_usage('/').percent
                }
            })
            
            # Load average (Unix-like systems)
            try:
                load1, load5, load15 = os.getloadavg()
                info["load_average"] = {
                    "1min": load1,
                    "5min": load5,
                    "15min": load15
                }
            except (AttributeError, OSError):
                info["load_average"] = "not_available"
        else:
            # Basic system info without psutil
            try:
                load1, load5, load15 = os.getloadavg()
                info["load_average"] = {
                    "1min": load1,
                    "5min": load5,
                    "15min": load15
                }
            except (AttributeError, OSError):
                info["load_average"] = "not_available"
                
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        info["error"] = str(e)
    
    return info

# Health check endpoint function
def run_health_checks() -> dict:
    """Run all health checks and return results"""
    results = {
        "timestamp": time.time(),
        "overall_status": "healthy",
        "checks": {}
    }
    
    # Individual check results
    checks = [
        ("server_load", lambda: not check_server_load()),
        ("ton_node", check_ton_node),
        ("payment_gateways", check_payment_gateways),
        ("database", check_database_connectivity)
    ]
    
    failed_checks = []
    
    for check_name, check_func in checks:
        try:
            results["checks"][check_name] = {
                "status": "pass" if check_func() else "fail",
                "timestamp": time.time()
            }
            if results["checks"][check_name]["status"] == "fail":
                failed_checks.append(check_name)
        except Exception as e:
            results["checks"][check_name] = {
                "status": "error",
                "error": str(e),
                "timestamp": time.time()
            }
            failed_checks.append(check_name)
    
    # Set overall status
    if failed_checks:
        results["overall_status"] = "unhealthy"
        results["failed_checks"] = failed_checks
    
    # Add system info
    results["system_info"] = get_system_info()
    
    return results