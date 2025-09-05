import logging
import time
import hmac
import jwt
import hashlib
import urllib.parse
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
from src.telegram.auth import get_authenticated_user_id
from src.database.mongo import get_user_data
from config import config
from src.database.mongo import get_user_activity, get_withdrawal_history

class SecurityException(Exception):
    """Custom exception for security-related errors"""
    pass

logger = logging.getLogger(__name__)

# Telegram Authentication
def validate_telegram_hash(init_data: str, bot_token: str) -> bool:
    """
    Validate Telegram Mini App initData using HMAC-SHA256 signature verification
    
    Args:
        init_data: The raw initData string from Telegram
        bot_token: Your Telegram bot token
        
    Returns:
        bool: True if validation passes, False otherwise
    """
    try:
        # Parse the initData string into key-value pairs
        parsed_data = {}
        for pair in init_data.split('&'):
            key, value = pair.split('=', 1)
            # URL decode the value
            decoded_value = urllib.parse.unquote(value)
            # Handle array values (like photo sizes)
            if key in parsed_data:
                if not isinstance(parsed_data[key], list):
                    parsed_data[key] = [parsed_data[key]]
                parsed_data[key].append(decoded_value)
            else:
                parsed_data[key] = decoded_value
        
        # Extract the hash and remove it from the dataset
        received_hash = parsed_data.get('hash', '')
        if not received_hash:
            logger.warning("No hash found in initData")
            return False
            
        # Create data-check-string
        data_check = []
        for key in sorted(parsed_data.keys()):
            if key == 'hash':
                continue
            value = parsed_data[key]
            # Handle array values as comma-separated strings
            if isinstance(value, list):
                value = ','.join(value)
            data_check.append(f"{key}={value}")
        
        data_check_string = "\n".join(data_check)
        
        # Compute secret key using Telegram's method
        secret_key = hmac.new(
            key=b'WebAppData',
            msg=bot_token.encode(),
            digestmod=hashlib.sha256
        ).digest()
        
        # Compute HMAC signature
        computed_hash = hmac.new(
            key=secret_key,
            msg=data_check_string.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()
        
        # Compare hashes in constant-time
        return hmac.compare_digest(computed_hash, received_hash)
    except Exception as e:
        logger.error(f"Telegram hash validation failed: {str(e)}")
        return False

# Request utilities
def get_user_id(request) -> int:
    """Get authenticated user ID from request with multiple fallbacks"""
    try:
        # 1. Check Telegram WebApp initData
        init_data = request.headers.get('X-Telegram-InitData') or request.args.get('initData')
        if init_data and config.TELEGRAM_TOKEN:
            # Parse user ID from validated initData
            if validate_telegram_hash(init_data, config.TELEGRAM_TOKEN):
                parsed = urllib.parse.parse_qs(init_data)
                user_data = parsed.get('user', ['{}'])[0]
                # Extract user ID from JSON-like string
                user_id_start = user_data.find('"id":') + 5
                user_id_end = user_data.find(',', user_id_start)
                if user_id_end == -1:
                    user_id_end = user_data.find('}', user_id_start)
                if user_id_start > 5 and user_id_end > user_id_start:
                    return int(user_data[user_id_start:user_id_end].strip())
        
        # 2. Check Authorization header (JWT token)
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(" ")[1]
            # Placeholder implementation - use real JWT validation
            try:
                # This would be replaced with actual JWT decoding
                parts = token.split(".")
                if len(parts) == 3:  # Standard JWT format
                    return int(parts[0])
            except Exception as e:
                logger.warning(f"JWT decoding failed: {str(e)}")
            
        # 3. Check session cookies
        session_id = request.cookies.get('session_id')
        if session_id:
            try:
                return int(session_id.split("_")[0])
            except:
                pass
                
        # 4. Check JSON body
        if request.json:
            user_id = request.json.get('user_id')
            if user_id:
                return int(user_id)
                
        # 5. Check query parameters
        user_id = request.args.get('user_id')
        if user_id:
            return int(user_id)
            
        logger.warning("No valid user ID found in request")
        return 0  # Default user ID for testing
    except Exception as e:
        logger.error(f"Error getting user ID: {str(e)}")
        return 0  # Default user ID for testing
    
# Add to security.py
def validate_ton_address(address: str) -> bool:
    """Basic TON address validator"""
    # Simplified validation - real implementation would use TON libraries
    if not address:
        return False
    return address.startswith(('EQ', 'UQ')) and len(address) == 48

def validate_game_request(request):
    init_data = request.headers.get('X-Telegram-InitData')
    if not validate_telegram_hash(init_data, config.TELEGRAM_TOKEN):
        raise PermissionError("Invalid Telegram hash")
    
    user_id = get_user_id(request)
    if is_abnormal_activity(user_id):
        raise SecurityException("Suspicious activity detected")

# Reusable for all games
def generate_security_token(user_id):
    payload = {'user_id': user_id, 'exp': datetime.utcnow() + timedelta(minutes=30)}
    return jwt.encode(payload, config.SECRET_KEY, algorithm='HS256')

def is_abnormal_activity(user_id: int) -> bool:
    """Check for suspicious activity patterns"""
    try:
        # Get recent user activity (last 24 hours)
        recent_activity = get_user_activity(user_id, limit=50)
        if not recent_activity:
            return False
            
        # 1. Multiple withdrawals check
        recent_withdrawals = [a for a in recent_activity if a.get('type') == 'withdrawal']
        if len(recent_withdrawals) > config.MAX_WITHDRAWALS_PER_DAY:
            logger.warning(f"Abnormal activity: Too many withdrawals ({len(recent_withdrawals)}) for user {user_id}")
            return True
            
        # 2. Geographic anomalies
        locations = {}
        for a in recent_activity:
            loc = a.get('ip_country')
            if loc:
                locations[loc] = locations.get(loc, 0) + 1
        if len(locations) > 3:  # Activity from >3 countries
            logger.warning(f"Abnormal activity: Multiple countries ({len(locations)}) for user {user_id}")
            return True
            
        # 3. Device switching
        devices = {a.get('device_id') for a in recent_activity if a.get('device_id')}
        if len(devices) > 3:  # Activity from >3 devices
            logger.warning(f"Abnormal activity: Multiple devices ({len(devices)}) for user {user_id}")
            return True
        
        return False
    except Exception as e:
        logger.error(f"Error checking abnormal activity: {str(e)}")
        return False
    
def wallet_connection_required(f):
    """
    Decorator to ensure user has a connected wallet
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = get_authenticated_user_id()
        if not user_id:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        # Check if user has connected wallet
        user_data = get_user_data(user_id)
        if not user_data or not user_data.get('wallet_address'):
            return jsonify({'success': False, 'error': 'Wallet not connected'}), 403
        
        return f(*args, **kwargs)
    return decorated_function

def secure_mask(value, show_first=6, show_last=4, min_length=10):
    """
    Mask sensitive information while showing partial content
    :param value: The value to mask
    :param show_first: Number of leading characters to show
    :param show_last: Number of trailing characters to show
    :param min_length: Minimum length to apply masking
    :return: Masked string
    """
    if not value:
        return "[EMPTY]"
    
    str_value = str(value)
    length = len(str_value)
    
    if length < min_length:
        return "[REDACTED]"
    
    if length <= (show_first + show_last):
        return str_value[:show_first] + "..." if length > show_first else str_value
    
    return f"{str_value[:show_first]}...{str_value[-show_last:]}"

# Add to security.py
def generate_session_token(user_id: int) -> str:
    """
    Generate a secure session token for game sessions
    
    Args:
        user_id: Telegram user ID
        
    Returns:
        str: JWT token containing user ID and expiration
    """
    try:
        # Create payload with user ID and expiration
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + timedelta(hours=24)  # 24-hour expiration
        }
        
        # Generate JWT token
        token = jwt.encode(
            payload,
            config.SECRET_KEY,
            algorithm='HS256'
        )
        
        return token
        
    except Exception as e:
        logger.error(f"Error generating session token: {str(e)}")
        # Fallback to simple token if JWT fails
        return f"session_{user_id}_{int(time.time())}"

# Fraud Detection System
class FraudDetectionSystem:
    def __init__(self):
        self.suspicion_threshold = config.FRAUD_SUSPICION_THRESHOLD
        self.ban_threshold = config.FRAUD_BAN_THRESHOLD
        self.activity_windows = {
            'short': 5 * 60,  # 5 minutes
            'medium': 60 * 60,  # 1 hour
            'long': 24 * 60 * 60  # 1 day
        }

    def detect_fraud(self, user_id: int) -> str:
        """Comprehensive fraud detection and action pipeline"""
        try:
            score = self.calculate_fraud_score(user_id)
            return self.take_action(user_id, score)
        except Exception as e:
            logger.error(f"Fraud detection failed for user {user_id}: {str(e)}")
            return "error"

    def calculate_fraud_score(self, user_id: int) -> float:
        """Calculate comprehensive fraud suspicion score"""
        suspicion_score = 0
        
        # Weighted components
        suspicion_score += self.analyze_click_velocity(user_id) * 0.4
        suspicion_score += self.analyze_device_fingerprint(user_id) * 0.3
        suspicion_score += self.analyze_withdrawal_patterns(user_id) * 0.3
        suspicion_score += self.detect_behavior_anomalies(user_id) * 0.2
        suspicion_score += self.analyze_network_patterns(user_id) * 0.2
        
        return min(suspicion_score, 1.0)  # Cap at 1.0

    def analyze_click_velocity(self, user_id: int) -> float:
        """Detect unnatural click patterns (0.0-1.0)"""
        try:
            activity = get_user_activity(user_id, limit=100)
            click_timestamps = [a['timestamp'].timestamp() for a in activity if a.get('type') == 'click']
            
            if len(click_timestamps) < 10:
                return 0.0  # Not enough data
                
            # Calculate time intervals
            intervals = []
            for i in range(1, len(click_timestamps)):
                intervals.append(click_timestamps[i] - click_timestamps[i-1])
            
            avg_interval = sum(intervals) / len(intervals)
            std_dev = (sum((x - avg_interval)**2 for x in intervals) / len(intervals))**0.5
            
            # Detection logic
            score = 0.0
            
            # Too consistent (bot-like)
            if std_dev < 0.05:
                score += 0.7
            
            # Too many actions in short time
            if len(click_timestamps) > config.MAX_CLICKS_PER_MINUTE * 5:
                score += 0.8
            
            # Burst detection (multiple clicks in <10ms)
            burst_count = sum(1 for interval in intervals if interval < 0.01)
            if burst_count / len(intervals) > 0.3:
                score += 0.6
                
            return min(score, 1.0)
        except Exception as e:
            logger.error(f"Click velocity analysis failed: {str(e)}")
            return 0.0

    def analyze_device_fingerprint(self, user_id: int) -> float:
        """Detect suspicious device configurations (0.0-1.0)"""
        try:
            device_data = self.get_device_fingerprint(user_id)
            score = 0.0
            
            # 1. Emulator detection
            if device_data.get('is_emulator', False):
                score += 0.4
            
            # 2. Multiple account detection
            if device_data.get('accounts_on_device', 1) > 3:
                score += 0.3
            
            # 3. Suspicious device settings
            if device_data.get('developer_mode', False):
                score += 0.2
            if device_data.get('mock_location', False):
                score += 0.3
            
            # 4. Unusual device characteristics
            if device_data.get('screen_density', 300) < 100:  # Unusually low
                score += 0.2
            if device_data.get('ram_size', 0) > 12:  # Suspiciously high for mobile
                score += 0.2
            
            return min(score, 1.0)
        except Exception as e:
            logger.error(f"Device analysis failed: {str(e)}")
            return 0.0

    def analyze_withdrawal_patterns(self, user_id: int) -> float:
        """Detect money laundering patterns (0.0-1.0)"""
        try:
            withdrawals = get_withdrawal_history(user_id)
            if len(withdrawals) < 3:
                return 0.0
                
            score = 0.0
            now = time.time()
            
            # 1. Micro-withdrawal testing
            test_withdrawals = sum(1 for w in withdrawals if w['amount'] < 0.01)
            if test_withdrawals > 2:
                score += 0.6
            
            # 2. Rapid withdrawal sequences
            recent_withdrawals = [w for w in withdrawals 
                                 if now - w['created_at'].timestamp() < self.activity_windows['long']]
            
            if len(recent_withdrawals) > config.MAX_WITHDRAWALS_PER_DAY:
                score += 0.8
            
            # 3. Destination clustering
            destinations = {}
            for w in recent_withdrawals:
                addr = w['address']
                destinations[addr] = destinations.get(addr, 0) + 1
            
            # Many withdrawals to same address
            for count in destinations.values():
                if count > 5:
                    score += 0.4
                    
            return min(score, 1.0)
        except Exception as e:
            logger.error(f"Withdrawal analysis failed: {str(e)}")
            return 0.0

    def detect_behavior_anomalies(self, user_id: int) -> float:
        """Detect abnormal behavior patterns (0.0-1.0)"""
        try:
            activity = get_user_activity(user_id, limit=500)
            if not activity:
                return 0.0
                
            score = 0.0
            
            # 1. Session analysis
            sessions = {}
            for event in activity:
                session_id = event.get('session_id')
                if session_id:
                    if session_id not in sessions:
                        sessions[session_id] = {
                            'start': event['timestamp'],
                            'end': event['timestamp']
                        }
                    else:
                        if event['timestamp'] < sessions[session_id]['start']:
                            sessions[session_id]['start'] = event['timestamp']
                        if event['timestamp'] > sessions[session_id]['end']:
                            sessions[session_id]['end'] = event['timestamp']
            
            session_count = len(sessions)
            if session_count > 0:
                total_duration = sum(
                    (sess['end'] - sess['start']).total_seconds()
                    for sess in sessions.values()
                )
                avg_session = total_duration / session_count
                
                # Suspiciously short sessions
                if avg_session < 30:
                    score += 0.5
            
            # 2. Always-active detection
            active_hours = {hour: 0 for hour in range(24)}
            for event in activity:
                hour = event['timestamp'].hour
                active_hours[hour] = active_hours.get(hour, 0) + 1
            
            if min(active_hours.values()) > 5:  # Activity every hour
                score += 0.7
            
            # 3. Reward-focused behavior
            reward_actions = sum(1 for a in activity if a.get('type') in ['ad_view', 'game_reward'])
            total_actions = len(activity)
            if total_actions > 0 and (reward_actions / total_actions) > 0.9:
                score += 0.4
            
            return min(score, 1.0)
        except Exception as e:
            logger.error(f"Behavior analysis failed: {str(e)}")
            return 0.0

    def analyze_network_patterns(self, user_id: int) -> float:
        """Detect network-level fraud (0.0-1.0)"""
        try:
            network_data = self.get_network_data(user_id)
            score = 0.0
            
            # 1. IP reputation check
            if network_data.get('ip_reputation_score', 100) < 20:
                score += 0.8
            
            # 2. VPN/Proxy detection
            if network_data.get('is_vpn', False) or network_data.get('is_proxy', False):
                score += 0.6
            
            # 3. Geographic inconsistencies
            if network_data.get('country') != network_data.get('registration_country'):
                score += 0.4
            
            # 4. Multiple account clustering
            if network_data.get('accounts_per_ip', 1) > 5:
                score += 0.7
                
            return min(score, 1.0)
        except Exception as e:
            logger.error(f"Network analysis failed: {str(e)}")
            return 0.0

    def take_action(self, user_id: int, score: float) -> str:
        """Apply security measures based on fraud score"""
        try:
            if score >= self.ban_threshold:
                self.ban_user(user_id, permanent=True)
                self.freeze_funds(user_id)
                logger.warning(f"Permanent ban for user {user_id} (score: {score:.2f})")
                return "permanent_ban"
            
            elif score >= self.suspicion_threshold:
                self.restrict_account(user_id)
                logger.warning(f"Temporary restrictions for user {user_id} (score: {score:.2f})")
                return "temporary_restriction"
            
            elif score > self.suspicion_threshold * 0.7:
                self.require_kyc(user_id)
                logger.info(f"KYC required for user {user_id} (score: {score:.2f})")
                return "kyc_required"
            
            return "no_action"
        except Exception as e:
            logger.error(f"Security action failed: {str(e)}")
            return "error"

    # Security actions (to be implemented with database calls)
    def ban_user(self, user_id: int, permanent: bool = False):
        """Ban user in database"""
        # Implementation would update user status
        logger.info(f"Banning user {user_id} ({'permanent' if permanent else 'temporary'})")
        
    def freeze_funds(self, user_id: int):
        """Freeze user's funds"""
        # Implementation would lock balance
        logger.info(f"Freezing funds for user {user_id}")
        
    def restrict_account(self, user_id: int):
        """Apply account restrictions"""
        # Implementation would set limits
        logger.info(f"Applying restrictions to user {user_id}")
        
    def require_kyc(self, user_id: int):
        """Trigger KYC verification"""
        # Implementation would initiate KYC flow
        logger.info(f"Requiring KYC for user {user_id}")

    # Data collection (stub implementations)
    def get_device_fingerprint(self, user_id: int) -> dict:
        """Get device characteristics (stub)"""
        # Real implementation: collect from client headers/mobile SDK
        return {
            'is_emulator': False,
            'accounts_on_device': 1,
            'developer_mode': False,
            'mock_location': False,
            'screen_density': 420,
            'ram_size': 6
        }

    def get_network_data(self, user_id: int) -> dict:
        """Get network characteristics (stub)"""
        # Real implementation: use IP analysis services
        return {
            'ip_reputation_score': 85,
            'is_vpn': False,
            'is_proxy': False,
            'country': 'US',
            'registration_country': 'US',
            'accounts_per_ip': 1
        }