GAME_LEVELS = {
    'clicker': [
        {"title": "Novice Clicker", "threshold": 500},
        {"title": "Speedy Gonzales", "threshold": 2500},
        {"title": "Master Tapper", "threshold": 10000},
        {"title": "Click Champion", "threshold": 50000},
        {"title": "God of Clicks", "threshold": 200000}
    ],
    'trivia': [
        {"title": "Rookie Scholar", "threshold": 100},
        {"title": "Quiz Wizard", "threshold": 500},
        {"title": "Trivia Master", "threshold": 2000},
        {"title": "Knowledge King", "threshold": 10000},
        {"title": "Oracle of Wisdom", "threshold": 50000}
    ],
    'trex': [
        {"title": "Dino Rookie", "threshold": 1000},
        {"title": "Canyon Runner", "threshold": 5000},
        {"title": "Obstacle Dodger", "threshold": 20000},
        {"title": "Prehistoric Speedster", "threshold": 100000},
        {"title": "T-Rex Master", "threshold": 500000}
    ],
    'edge_surf': [
        {"title": "Web Newbie", "threshold": 500},
        {"title": "Browser Surfer", "threshold": 2500},
        {"title": "Internet Explorer", "threshold": 10000},
        {"title": "Cloud Navigator", "threshold": 50000},
        {"title": "Edge Lord", "threshold": 250000}
    ],
    'spin': [
        {"title": "Lucky Beginner", "threshold": 10},
        {"title": "Wheel Spinner", "threshold": 50},
        {"title": "Fortune Seeker", "threshold": 200},
        {"title": "Jackpot Hunter", "threshold": 1000},
        {"title": "Casino King", "threshold": 5000}
    ]
}

def get_user_level(game_type: str, score: int) -> dict:
    """Get user's current level and progress"""
    levels = GAME_LEVELS.get(game_type, [])
    current_level = {"title": "New Player", "progress": 0}
    
    for level in levels:
        if score >= level['threshold']:
            current_level = level
        else:
            # Calculate progress to next level
            prev_threshold = levels[levels.index(level)-1]['threshold'] if levels.index(level) > 0 else 0
            range_to_next = level['threshold'] - prev_threshold
            current_progress = (score - prev_threshold) / range_to_next
            current_level = {
                **current_level,
                "next_level": level['title'],
                "progress": min(round(current_progress * 100), 100)
            }
            break
    
    return current_level