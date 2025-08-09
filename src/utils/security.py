import logging
import time
from datetime import datetime, timedelta
from flask import request
from config import Config
from src.database.firebase import get_user_activity, get_withdrawal_history

logger = logging.getLogger(__name__)

# Request utilities
def get_user_id(request):
    """Get user ID from request using multiple fallback methods"""
    try:
        # 1. Check Authorization header (JWT token)
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(" ")[1]
            # In production: decode JWT to get user_id
            # Placeholder implementation
            return int(token.split("-")[0]) if "-" in token else None
            
        # 2. Check session cookies
        session_id = request.cookies.get('session_id')
        if session_id:
            # Placeholder: session lookup would happen here
            return int(session_id.split("_")[0]) if "_" in session_id else None
            
        # 3. Check JSON body
        if request.json:
            user_id = request.json.get('user_id')
            if user_id:
                return int(user_id)
                
        # 4. Check query parameters
        user_id = request.args.get('user_id')
        if user_id:
            return int(user_id)
            
        logger.warning("No user ID found in request")
        return None
    except Exception as e:
        logger.error(f"Error getting user ID: {str(e)}")
        return None

def is_abnormal_activity(user_id):
    """Check for suspicious activity patterns"""
    try:
        # Get recent user activity
        recent_activity = get_user_activity(user_id, limit=20)
        
        # Simple check: if more than 5 withdrawals in last hour
        recent_withdrawals = [a for a in recent_activity if a.get('type') == 'withdrawal']
        if len(recent_withdrawals) > 5:
            return True
            
        # More sophisticated checks would go here:
        # - Unusual transaction amounts
        # - Geographic anomalies
        # - Device fingerprint mismatches
        
        return False
    except Exception as e:
        logger.error(f"Error checking abnormal activity: {str(e)}")
        return False

# Fraud Detection System
class FraudDetectionSystem:
    def __init__(self):
        self.suspicion_threshold = Config.FRAUD_SUSPICION_THRESHOLD
        self.ban_threshold = Config.FRAUD_BAN_THRESHOLD
        self.activity_windows = {
            'short': 5 * 60,  # 5 minutes
            'medium': 60 * 60,  # 1 hour
            'long': 24 * 60 * 60  # 1 day
        }

    def detect_farming_patterns(self, user_id):
        """Comprehensive fraud detection scoring"""
        suspicion_score = 0
        
        # 1. Click velocity analysis
        suspicion_score += self.analyze_click_velocity(user_id) * 0.4
        
        # 2. Device fingerprinting
        suspicion_score += self.analyze_device_fingerprint(user_id) * 0.3
        
        # 3. Withdrawal patterns
        suspicion_score += self.analyze_withdrawal_patterns(user_id) * 0.3
        
        # 4. Behavior anomalies
        suspicion_score += self.detect_behavior_anomalies(user_id) * 0.2
        
        # 5. Network analysis
        suspicion_score += self.analyze_network_patterns(user_id) * 0.2
        
        return min(suspicion_score, 1.0)  # Cap at 1.0

    def analyze_click_velocity(self, user_id):
        """Detect unnatural click patterns"""
        activity = get_user_activity(user_id, window=self.activity_windows['short'])
        click_timestamps = [a['timestamp'] for a in activity if a.get('type') == 'click']
        
        if len(click_timestamps) < 10:
            return 0  # Not enough data
        
        # Calculate time intervals between clicks
        intervals = []
        for i in range(1, len(click_timestamps)):
            intervals.append(click_timestamps[i] - click_timestamps[i-1])
        
        avg_interval = sum(intervals) / len(intervals) if intervals else 0
        std_dev = (sum((x - avg_interval)**2 for x in intervals) / len(intervals))**0.5 if intervals else 0
        
        # Detection logic
        score = 0
        
        # Too consistent (bot-like)
        if std_dev < 0.05 and avg_interval > 0:
            score += 0.7
        
        # Too many actions in short time
        if len(click_timestamps) > Config.MAX_CLICKS_PER_MINUTE * 5:
            score += 0.8
        
        # Burst detection
        burst_count = sum(1 for interval in intervals if interval < 0.01)
        if intervals and (burst_count / len(intervals)) > 0.3:
            score += 0.6
            
        return min(score, 1.0)

    def analyze_device_fingerprint(self, user_id):
        """Detect suspicious device configurations"""
        device_data = self.get_device_fingerprint(user_id)
        score = 0
        
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

    def analyze_withdrawal_patterns(self, user_id):
        """Detect money laundering patterns"""
        withdrawals = get_withdrawal_history(user_id)
        if len(withdrawals) < 3:
            return 0
        
        score = 0
        now = time.time()
        
        # 1. Micro-withdrawal testing
        test_withdrawals = sum(1 for w in withdrawals if w['amount'] < 0.01)
        if test_withdrawals > 2:
            score += 0.6
        
        # 2. Rapid withdrawal sequences
        recent_withdrawals = [w for w in withdrawals if now - w['created_at'].timestamp() < self.activity_windows['long']]
        
        if len(recent_withdrawals) > Config.MAX_WITHDRAWALS_PER_DAY:
            score += 0.8
        
        # 3. Destination clustering
        destinations = {}
        for w in recent_withdrawals:
            destinations[w['address']] = destinations.get(w['address'], 0) + 1
        
        # Many small withdrawals to same address
        for addr, count in destinations.items():
            if count > 5:
                score += 0.4
                
        return min(score, 1.0)

    def detect_behavior_anomalies(self, user_id):
        """Detect abnormal user behavior patterns"""
        activity = get_user_activity(user_id, window=self.activity_windows['long'])
        score = 0
        
        # 1. Unnatural session patterns
        sessions = {}
        for event in activity:
            if 'session_id' in event:
                session_id = event['session_id']
                if session_id not in sessions:
                    sessions[session_id] = {'start': event['timestamp'], 'end': event['timestamp']}
                else:
                    if event['timestamp'] < sessions[session_id]['start']:
                        sessions[session_id]['start'] = event['timestamp']
                    if event['timestamp'] > sessions[session_id]['end']:
                        sessions[session_id]['end'] = event['timestamp']
        
        session_count = len(sessions)
        total_duration = sum(sess['end'] - sess['start'] for sess in sessions.values())
        
        if session_count > 50:
            avg_session = total_duration / session_count
            if avg_session < 30:  # Suspiciously short sessions
                score += 0.5
        
        # 2. Always active detection
        active_hours = {hour: 0 for hour in range(24)}
        for event in activity:
            hour = datetime.fromtimestamp(event['timestamp']).hour
            active_hours[hour] = active_hours.get(hour, 0) + 1
        
        if min(active_hours.values()) > 5:  # At least 5 activities every hour
            score += 0.7
        
        # 3. Reward-focused behavior
        reward_actions = sum(1 for a in activity if a.get('type') in ['ad_view', 'game_reward'])
        if activity and (reward_actions / len(activity)) > 0.9:
            score += 0.4
        
        return min(score, 1.0)

    def analyze_network_patterns(self, user_id):
        """Detect network-level fraud patterns"""
        connections = self.get_network_data(user_id)
        score = 0
        
        # 1. IP reputation check
        if connections.get('ip_reputation_score', 100) < 20:  # 0-100 scale
            score += 0.8
        
        # 2. VPN/Proxy detection
        if connections.get('is_vpn', False) or connections.get('is_proxy', False):
            score += 0.6
        
        # 3. Geographic inconsistencies
        if connections.get('country') != connections.get('registration_country'):
            score += 0.4
        
        # 4. Multiple account clustering
        if connections.get('accounts_per_ip', 1) > 5:
            score += 0.7
            
        return min(score, 1.0)

    def take_action(self, user_id, score):
        """Apply appropriate security measures"""
        if score >= self.ban_threshold:
            self.ban_user(user_id, permanent=True)
            self.freeze_funds(user_id)
            return "permanent_ban"
        elif score >= self.suspicion_threshold:
            self.restrict_account(user_id)
            return "temporary_restriction"
        elif score > self.suspicion_threshold * 0.7:
            self.require_kyc(user_id)
            return "kyc_required"
        return "no_action"

    # Security actions (would connect to database)
    def ban_user(self, user_id, permanent=False):
        logger.warning(f"Banning user {user_id} ({'permanent' if permanent else 'temporary'})")
        # Implementation would update user status in database
        
    def freeze_funds(self, user_id):
        logger.warning(f"Freezing funds for user {user_id}")
        # Implementation would lock user's balance
        
    def restrict_account(self, user_id):
        logger.warning(f"Applying restrictions to user {user_id}")
        # Implementation would set account limitations
        
    def require_kyc(self, user_id):
        logger.info(f"Requiring KYC for user {user_id}")
        # Implementation would trigger KYC verification

    # Data collection helpers
    def get_device_fingerprint(self, user_id):
        """Get device characteristics (stub implementation)"""
        # In production: collect from client headers or mobile SDK
        return {
            'is_emulator': False,
            'accounts_on_device': 1,
            'developer_mode': False,
            'mock_location': False,
            'screen_density': 420,
            'ram_size': 6
        }

    def get_network_data(self, user_id):
        """Get network characteristics (stub implementation)"""
        # In production: use IP analysis services
        return {
            'ip_reputation_score': 85,
            'is_vpn': False,
            'is_proxy': False,
            'country': 'US',
            'registration_country': 'US',
            'accounts_per_ip': 1
        }