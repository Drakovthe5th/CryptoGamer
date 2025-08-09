import time
from datetime import datetime, timedelta
from config import Config
from src.database.firebase import get_user_activity, get_withdrawal_history

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
        """Comprehensive fraud detection system"""
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
        
        return suspicion_score

    def analyze_click_velocity(self, user_id):
        """Detect unnatural click patterns"""
        activity = get_user_activity(user_id, window=self.activity_windows['short'])
        clicks = activity.get('clicks', [])
        
        if len(clicks) < 10:
            return 0  # Not enough data
        
        # Calculate statistics
        intervals = [b - a for a, b in zip(clicks[:-1], clicks[1:])]
        avg_interval = sum(intervals) / len(intervals)
        std_dev = (sum((x - avg_interval)**2 for x in intervals) / len(intervals))**0.5
        
        # Detection logic
        score = 0
        
        # Too consistent (bot-like)
        if std_dev < 0.05:
            score += 0.7
        
        # Too many actions in short time
        if len(clicks) > Config.MAX_CLICKS_PER_MINUTE * 5:
            score += 0.8
        
        # Burst detection
        burst_count = sum(1 for interval in intervals if interval < 0.01)
        if burst_count / len(intervals) > 0.3:
            score += 0.6
            
        return min(score, 1.0)

    def analyze_device_fingerprint(self, user_id):
        """Detect suspicious device configurations"""
        device_data = get_device_fingerprint(user_id)
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
        if device_data.get('screen_density') < 100:  # Unusually low
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
        
        # 1. Micro-withdrawal testing
        test_withdrawals = sum(1 for w in withdrawals if w['amount'] < 0.01)
        if test_withdrawals > 2:
            score += 0.6
        
        # 2. Rapid withdrawal sequences
        now = time.time()
        recent_withdrawals = [w for w in withdrawals if now - w['time'] < self.activity_windows['long']]
        
        if len(recent_withdrawals) > Config.MAX_WITHDRAWALS_PER_DAY:
            score += 0.8
        
        # 3. Destination clustering
        destinations = {}
        for w in withdrawals:
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
        if activity.get('session_count', 0) > 50:
            avg_session = activity['total_duration'] / activity['session_count']
            if avg_session < 30:  # Suspiciously short sessions
                score += 0.5
        
        # 2. Always active detection
        time_ranges = activity.get('active_hours', {})
        if min(time_ranges.values()) > 5:  # At least 5 activities every hour
            score += 0.7
        
        # 3. Reward-focused behavior
        if activity.get('reward_actions', 0) / activity.get('total_actions', 1) > 0.9:
            score += 0.4
        
        return min(score, 1.0)

    def analyze_network_patterns(self, user_id):
        """Detect network-level fraud patterns"""
        connections = get_network_data(user_id)
        score = 0
        
        # 1. IP reputation check
        if connections.get('ip_reputation_score', 0) < 20:  # 0-100 scale
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
            # Permanent ban with fund freeze
            ban_user(user_id, permanent=True)
            freeze_funds(user_id)
            return "permanent_ban"
        
        elif score >= self.suspicion_threshold:
            # Temporary restrictions
            restrict_account(user_id, 
                             withdrawal_limit=0.1,
                             reward_factor=0.5,
                             duration=timedelta(days=7))
            return "temporary_restriction"
        
        elif score > self.suspicion_threshold * 0.7:
            # Enhanced verification
            require_kyc(user_id)
            return "kyc_required"
        
        return "no_action"

# Helper functions (would be implemented elsewhere)
def get_device_fingerprint(user_id):
    # Implementation would collect device characteristics
    return {
        'is_emulator': False,
        'accounts_on_device': 1,
        'developer_mode': False,
        'mock_location': False,
        'screen_density': 420,
        'ram_size': 6
    }

def get_network_data(user_id):
    # Implementation would analyze network characteristics
    return {
        'ip_reputation_score': 85,
        'is_vpn': False,
        'is_proxy': False,
        'country': 'US',
        'registration_country': 'US',
        'accounts_per_ip': 1
    }