import statistics
from src.database.firebase import get_user_activity

class AntiCheatSystem:
    def detect_farming(self, user_id):
        """Detect artificial engagement patterns"""
        activity = get_user_activity(user_id)
        
        patterns = {
            'click_velocity': self.calculate_click_suspicion(activity.get('click_intervals', [])),
            'session_similarity': self.calculate_session_similarity(activity.get('sessions', [])),
            'ip_reputation': self.check_ip_reputation(activity.get('ip_addresses', []))
        }
        
        # Mark as suspicious if any pattern exceeds threshold
        return any(score > 0.7 for score in patterns.values())
    
    def calculate_click_suspicion(self, click_intervals):
        """Measure consistency of click intervals"""
        if len(click_intervals) < 5:
            return 0
            
        stdev = statistics.stdev(click_intervals)
        # Low stdev indicates robotic consistency
        return 1 - min(stdev, 1.0)  # Normalize to 0-1 suspicion score
    
    def calculate_session_similarity(self, sessions):
        """Check for identical session patterns"""
        # Placeholder - real implementation would use ML
        if len(sessions) < 3:
            return 0
            
        durations = [s['duration'] for s in sessions]
        if max(durations) - min(durations) < 5:
            return 0.8  # Highly similar sessions
            
        return 0.2
    
    def check_ip_reputation(self, ip_addresses):
        """Check IP addresses for known farming networks"""
        # Placeholder - would integrate with IP reputation service
        if len(set(ip_addresses)) > 5:
            return 0.9  # Too many IPs in short time
            
        return 0.1