import time
import statistics
from src.database.mongo import get_user_activity
from src.utils.validators import is_rate_limited, validate_credentials_format, detect_suspicious_payment_pattern

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
    
    def validate_edge_surf(session_data: dict) -> bool:
        # Validate play duration
        play_duration = session_data['endTime'] - session_data['startTime']
        if play_duration > 3600 * 1000:  # 1 hour in ms
            return False
    
        # Validate input frequency
        inputs = session_data['userActions']
        avg_input_interval = play_duration / len(inputs) if inputs else 0
        if avg_input_interval < 50:  # 50ms between inputs
            return False
        
        return True

    
    def detect_edge_surf_cheat(session_data):
        # Check for unrealistic play duration
        play_duration = session_data['endTime'] - session_data['startTime']
        if play_duration > 3600:  # 1 hour
            return True
        
        # Check input pattern consistency
        inputs = session_data['userActions']
        if len(inputs) < 10:  # Too few inputs for gameplay
            return True
        
        return False
    
    def validate_trex_runner(session_data: dict) -> bool:
        # Game-specific validation
        distance = session_data.get('distance', 0)
        jump_count = session_data.get('jump_count', 0)
        play_duration = session_data['endTime'] - session_data['startTime']
        
        # Validate distance consistency
        if distance > 10000:  # Impossible distance
            return False
            
        # Validate jump frequency
        jumps_per_second = jump_count / (play_duration / 1000)
        if jumps_per_second > 5:  # Max 5 jumps/second
            return False
            
        # Validate progress correlation
        if distance > 1000 and jump_count < 3:
            return False
            
        return True
    
    def validate_clicker(session_data: dict) -> bool:
        clicks = session_data.get('clicks', 0)
        auto_clicks = session_data.get('auto_clicks', 0)
        play_duration = session_data['endTime'] - session_data['startTime']
        
        # Validate click rate
        clicks_per_second = clicks / (play_duration / 1000)
        if clicks_per_second > 20:  # Max 20 clicks/second
            return False
            
        # Validate autoclicker consistency
        if auto_clicks > 0 and clicks_per_second < 0.5:
            return False
            
        # Validate score progression
        if session_data['score'] > (clicks + auto_clicks) * 100:
            return False
            
        return True
    
    def validate_trivia(session_data: dict) -> bool:
        correct = session_data.get('correct', 0)
        total = session_data.get('total', 0)
        answer_times = session_data.get('answer_times', [])
        
        # Validate answer speed
        if any(t < 500 for t in answer_times):  # <500ms per answer
            return False
            
        # Validate accuracy consistency
        if correct == total and total > 20:  # Perfect score on long quiz
            return False
            
        # Validate time per question
        total_time = session_data['endTime'] - session_data['startTime']
        avg_time = total_time / total if total > 0 else 0
        if avg_time < 1000:  # <1 second per question
            return False
            
        return True
    
    def validate_spin(session_data: dict) -> bool:
        spins = session_data.get('spins', 0)
        wins = session_data.get('wins', 0)
        play_duration = session_data['endTime'] - session_data['startTime']
        
        # Validate spin frequency
        spins_per_minute = spins / (play_duration / 60000)
        if spins_per_minute > 120:  # Max 2 spins/second
            return False
            
        # Validate win ratio
        if wins > spins * 0.5:  # >50% win rate
            return False
            
        # Validate coin consistency
        if session_data['coins'] > (spins * 10):
            return False
            
        return True
    
    def validate_game_score(user_id, game_type, reported_score):
        from src.database.game_db import get_session_data
        session = get_session_data(user_id, game_type)
        
        # Calculate max possible score based on session duration
        max_scores = {
            'clicker': 5000,  # 5000 clicks/hr
            'trex': 10000,    # 10000 points/hr
            'trivia': 500,     # 500 correct answers/hr
            'spin': 300,       # 300 spins/hr
            'edge_surf': 2000  # 2000 points/hr
        }
        
        duration = (session['end_time'] - session['start_time']).total_seconds()
        max_possible = max_scores[game_type] * (duration / 3600)
        
        if reported_score > max_possible * 1.2:  # Allow 20% tolerance
            return False
        return True
    
    def validate_payment_request(user_id, credentials):
        """Validate payment request to prevent fraud"""
        # Check rate limiting
        if is_rate_limited(f"payment_{user_id}", max_attempts=5, period=3600):
            return False
        
        # Validate credentials format
        if not validate_credentials_format(credentials):
            return False
        
        # Check for suspicious patterns
        if detect_suspicious_payment_pattern(user_id, credentials):
            return False
        
        return True
class AdValidator:
    def __init__(self):
        self.ad_events = {}
    
    def validate_ad_request(self, user_id, slot_name):
        key = f"{user_id}:{slot_name}"
        current_time = time.time()
        
        # Allow at most 1 ad per minute per slot per user
        if key in self.ad_events and current_time - self.ad_events[key] < 60:
            return False
            
        self.ad_events[key] = current_time
        return True