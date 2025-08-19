import logging
import os
import time
import asyncio
import requests
from datetime import datetime
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
        from src.integrations.tonE2 import ton_wallet
        
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
                
                # Check for low balance warning
                if balance < getattr(config, 'MIN_HOT_BALANCE', 1.0):
                    send_alert_to_admin(f"⚠️ TON wallet low balance: {balance:.6f} TON")
                    
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
                logger.info(f"M-PESA gateway: {'OK' if mpesa_ok else 'DOWN'}")
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
                logger.info(f"PayPal gateway: {'OK' if paypal_ok else 'DOWN'}")
            except Exception as e:
                logger.error(f"PayPal connectivity check failed: {e}")
                paypal_ok = False
        
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
        from src.database.mongo import db
        
        # Simple connectivity test - try to read a document
        test_result = db.collection('health_check').limit(1).get()
        logger.info("Firebase database connectivity: OK")
        return True
        
    except Exception as e:
        logger.error(f"Database connectivity check failed: {e}")
        send_alert_to_admin(f"🔥 Database connectivity issue: {str(e)}")
        return False

def check_external_apis() -> dict:
    """Check external API connectivity"""
    api_status = {}
    
    # Check DexScreener API
    try:
        response = requests.get(
            "https://api.dexscreener.com/latest/dex/tokens/So11111111111111111111111111111111111111112",
            timeout=10
        )
        api_status['dexscreener'] = {
            'status': 'OK' if response.status_code == 200 else 'DOWN',
            'response_time': response.elapsed.total_seconds() if hasattr(response, 'elapsed') else 0
        }
        logger.info(f"DexScreener API: {api_status['dexscreener']['status']}")
    except Exception as e:
        api_status['dexscreener'] = {'status': 'ERROR', 'error': str(e)}
        logger.error(f"DexScreener API check failed: {e}")
    
    # Check CoinGecko API (if used)
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/ping",
            timeout=10
        )
        api_status['coingecko'] = {
            'status': 'OK' if response.status_code == 200 else 'DOWN',
            'response_time': response.elapsed.total_seconds() if hasattr(response, 'elapsed') else 0
        }
        logger.info(f"CoinGecko API: {api_status['coingecko']['status']}")
    except Exception as e:
        api_status['coingecko'] = {'status': 'ERROR', 'error': str(e)}
        logger.error(f"CoinGecko API check failed: {e}")
    
    return api_status

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
    
    # External API checks (don't fail overall health for API issues)
    try:
        api_status = check_external_apis()
        failed_apis = [api for api, status in api_status.items() if status.get('status') != 'OK']
        if failed_apis:
            logger.warning(f"External API issues: {', '.join(failed_apis)}")
            # Don't add to issues list as these are warnings, not critical failures
    except Exception as e:
        logger.error(f"External API check error: {e}")
    
    if issues:
        logger.warning(f"Health check issues found: {', '.join(issues)}")
        return True
    
    logger.info("All critical health checks passed")
    return False

def send_alert_to_admin(message: str):
    """Send alert to admin via Telegram"""
    try:
        if hasattr(config, 'ADMIN_USER_ID') and config.ADMIN_USER_ID:
            asyncio.create_task(send_telegram_message(config.ADMIN_USER_ID, message))
        logger.warning(f"ALERT: {message}")
    except Exception as e:
        logger.error(f"Failed to send alert: {e}")

def get_system_info() -> dict:
    """Get comprehensive system information"""
    info = {
        "timestamp": time.time(),
        "datetime": datetime.now().isoformat(),
        "psutil_available": PSUTIL_AVAILABLE
    }
    
    try:
        if PSUTIL_AVAILABLE:
            # Detailed system info with psutil
            info.update({
                "cpu_percent": psutil.cpu_percent(interval=1),
                "cpu_count": psutil.cpu_count(),
                "memory": {
                    "total": psutil.virtual_memory().total,
                    "available": psutil.virtual_memory().available,
                    "percent": psutil.virtual_memory().percent,
                    "used": psutil.virtual_memory().used
                },
                "disk": {
                    "total": psutil.disk_usage('/').total,
                    "free": psutil.disk_usage('/').free,
                    "percent": psutil.disk_usage('/').percent,
                    "used": psutil.disk_usage('/').used
                },
                "network": {
                    "bytes_sent": psutil.net_io_counters().bytes_sent,
                    "bytes_recv": psutil.net_io_counters().bytes_recv,
                    "packets_sent": psutil.net_io_counters().packets_sent,
                    "packets_recv": psutil.net_io_counters().packets_recv
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

def get_wallet_info() -> dict:
    """Get TON wallet information"""
    try:
        from src.integrations.tonE2 import ton_wallet
        
        if not ton_wallet.initialized:
            return {"status": "not_initialized"}
        
        # Get wallet status synchronously
        balance = asyncio.run(ton_wallet.get_balance(force_update=True))
        health = asyncio.run(ton_wallet.health_check())
        
        return {
            "status": "initialized",
            "address": ton_wallet.get_address(),
            "balance": balance,
            "healthy": health,
            "network": "testnet" if ton_wallet.is_testnet else "mainnet",
            "last_balance_check": ton_wallet.last_balance_check.isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get wallet info: {e}")
        return {"status": "error", "error": str(e)}

# Health check endpoint function
def run_health_checks() -> dict:
    """Run all health checks and return results"""
    start_time = time.time()
    
    results = {
        "timestamp": time.time(),
        "datetime": datetime.now().isoformat(),
        "overall_status": "healthy",
        "checks": {},
        "system_info": {},
        "wallet_info": {},
        "external_apis": {},
        "execution_time": 0
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
        check_start = time.time()
        try:
            check_result = check_func()
            results["checks"][check_name] = {
                "status": "pass" if check_result else "fail",
                "timestamp": time.time(),
                "execution_time": round(time.time() - check_start, 3)
            }
            if results["checks"][check_name]["status"] == "fail":
                failed_checks.append(check_name)
        except Exception as e:
            results["checks"][check_name] = {
                "status": "error",
                "error": str(e),
                "timestamp": time.time(),
                "execution_time": round(time.time() - check_start, 3)
            }
            failed_checks.append(check_name)
    
    # Set overall status
    if failed_checks:
        results["overall_status"] = "unhealthy"
        results["failed_checks"] = failed_checks
    
    # Add additional information
    try:
        results["system_info"] = get_system_info()
    except Exception as e:
        results["system_info"] = {"error": str(e)}
    
    try:
        results["wallet_info"] = get_wallet_info()
    except Exception as e:
        results["wallet_info"] = {"error": str(e)}
    
    try:
        results["external_apis"] = check_external_apis()
    except Exception as e:
        results["external_apis"] = {"error": str(e)}
    
    results["execution_time"] = round(time.time() - start_time, 3)
    
    return results

def cleanup_logs(max_age_days: int = 7) -> bool:
    """Clean up old log files"""
    try:
        import glob
        from pathlib import Path
        
        log_dir = Path("logs")
        if not log_dir.exists():
            logger.info("No logs directory found")
            return True
        
        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
        cleaned_count = 0
        
        for log_file in log_dir.glob("*.log*"):
            if log_file.stat().st_mtime < cutoff_time:
                log_file.unlink()
                cleaned_count += 1
        
        logger.info(f"Cleaned up {cleaned_count} old log files")
        return True
        
    except Exception as e:
        logger.error(f"Log cleanup failed: {e}")
        return False

def restart_services() -> bool:
    """Restart critical services (placeholder)"""
    try:
        logger.info("Restarting services...")
        
        # Restart TON wallet connection
        from src.integrations.tonE2 import ton_wallet
        asyncio.run(ton_wallet.initialize())
        
        logger.info("Services restarted successfully")
        return True
        
    except Exception as e:
        logger.error(f"Service restart failed: {e}")
        return False

# CLI interface for standalone usage
if __name__ == "__main__":
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="TON Trading Bot Maintenance")
    parser.add_argument("--action", choices=[
        "health", "cleanup-logs", "restart", "system-info", "wallet-info"
    ], default="health", help="Action to perform")
    parser.add_argument("--output", help="Output file for JSON results")
    parser.add_argument("--days", type=int, default=7, help="Days for cleanup operations")
    
    args = parser.parse_args()
    
    if args.action == "health":
        results = run_health_checks()
        output = json.dumps(results, indent=2)
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(output)
            print(f"Health check results saved to {args.output}")
        else:
            print(output)
    
    elif args.action == "cleanup-logs":
        success = cleanup_logs(args.days)
        print(f"Log cleanup: {'SUCCESS' if success else 'FAILED'}")
    
    elif args.action == "restart":
        success = restart_services()
        print(f"Service restart: {'SUCCESS' if success else 'FAILED'}")
    
    elif args.action == "system-info":
        info = get_system_info()
        output = json.dumps(info, indent=2)
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(output)
            print(f"System info saved to {args.output}")
        else:
            print(output)
    
    elif args.action == "wallet-info":
        info = get_wallet_info()
        output = json.dumps(info, indent=2)
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(output)
            print(f"Wallet info saved to {args.output}")
        else:
            print(output)