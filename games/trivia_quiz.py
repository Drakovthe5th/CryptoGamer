import random
import time
from .base_game import BaseGame

class TriviaQuiz(BaseGame):
    def __init__(self):
        super().__init__("trivia")
        self.questions = self.load_questions()
        self.question_time = 30  # Seconds per question
        self.difficulty_multiplier = {
            "easy": 1.0,
            "medium": 1.5,
            "hard": 2.0
        }
    
    def load_questions(self):
        return [
            {
                "id": 1,
                "question": "What blockchain consensus does TON use?",
                "options": ["Proof of Work", "Proof of Stake", "Byzantine Fault Tolerance", "Proof-of-Stake with Sharding"],
                "correct": 3,
                "difficulty": "medium",
                "category": "Blockchain"
            },
            {
                "id": 2,
                "question": "What is the native cryptocurrency of TON?",
                "options": ["TON Coin", "Toncoin", "Gram", "Telegram Coin"],
                "correct": 1,
                "difficulty": "easy",
                "category": "Crypto"
            },
            {
                "id": 3,
                "question": "What does TON stand for?",
                "options": ["Telegram Open Network", "The Open Network", "Token Open Network", "Telegram Operating Network"],
                "correct": 1,
                "difficulty": "easy",
                "category": "General"
            },
            {
                "id": 4,
                "question": "What unique feature does TON have?",
                "options": ["Instant Hypercube Routing", "Quantum Resistance", "Infinite Sharding", "Telegram Integration"],
                "correct": 2,
                "difficulty": "hard",
                "category": "Technology"
            },
            {
                "id": 5,
                "question": "What is the transaction speed of TON?",
                "options": ["1,000 TPS", "10,000 TPS", "100,000 TPS", "1,000,000 TPS"],
                "correct": 3,
                "difficulty": "medium",
                "category": "Performance"
            },
            {
                "id": 6,
                "question": "Who originally developed TON?",
                "options": ["Vitalik Buterin", "Telegram Team", "The Open Network Foundation", "Durov Brothers"],
                "correct": 1,
                "difficulty": "easy",
                "category": "History"
            },
            {
                "id": 7,
                "question": "What programming language is used for TON smart contracts?",
                "options": ["Solidity", "Rust", "FunC", "Move"],
                "correct": 2,
                "difficulty": "medium",
                "category": "Development"
            },
            {
                "id": 8,
                "question": "What is TON Storage?",
                "options": ["A decentralized file storage", "A crypto wallet", "A token standard", "A consensus mechanism"],
                "correct": 0,
                "difficulty": "medium",
                "category": "Features"
            },
            {
                "id": 9,
                "question": "What is TON DNS?",
                "options": ["Domain Name System for TON", "Data Network Service", "Decentralized Naming Standard", "Digital Naming System"],
                "correct": 0,
                "difficulty": "medium",
                "category": "Features"
            },
            {
                "id": 10,
                "question": "What is the smallest unit of TON?",
                "options": ["mTON", "nanoTON", "TONwei", "Gram"],
                "correct": 1,
                "difficulty": "easy",
                "category": "Crypto"
            }
        ]
    
    def get_init_data(self, user_id):
        return {
            **super().get_init_data(user_id),
            "instructions": "Answer questions correctly to earn TON coins!",
            "time_per_question": self.question_time,
            "reward_info": "Earn 0.001 TON per correct answer (more for harder questions)"
        }
    
    def start_game(self, user_id):
        super().start_game(user_id)
        self.players[user_id]["questions_answered"] = 0
        self.players[user_id]["correct_answers"] = 0
        self.players[user_id]["current_question"] = None
        return {
            "status": "started",
            "question": self.get_random_question()
        }
    
    def handle_action(self, user_id, action, data):
        player = self.players.get(user_id)
        if not player or not player["active"]:
            return {"error": "Game not active"}
        
        if action == "answer":
            question_id = data["question_id"]
            selected = data["selected"]
            question = next((q for q in self.questions if q["id"] == question_id), None)
            
            if not question:
                return {"error": "Invalid question"}
            
            # Check if answer is correct
            correct = selected == question["correct"]
            
            # Update stats
            player["questions_answered"] += 1
            if correct:
                player["correct_answers"] += 1
                
                # Calculate reward based on difficulty
                multiplier = self.difficulty_multiplier.get(question["difficulty"], 1.0)
                reward = 0.001 * multiplier
                player["score"] += reward
            
            return {
                "correct": correct,
                "correct_index": question["correct"],
                "score": player["score"],
                "reward": reward if correct else 0,
                "next_question": self.get_random_question(),
                "stats": {
                    "answered": player["questions_answered"],
                    "correct": player["correct_answers"]
                }
            }
        
        return {"error": "Invalid action"}
    
    def get_random_question(self):
        return random.choice(self.questions)
    
    def end_game(self, user_id):
        player = self.players.get(user_id)
        if not player or not player["active"]:
            return {"error": "Game not active"}
        
        player["active"] = False
        
        # Calculate final reward
        base_reward = player["score"]
        bonus = player["correct_answers"] * 0.0005
        total_reward = base_reward + bonus
        
        return {
            "status": "completed",
            "stats": {
                "total_questions": player["questions_answered"],
                "correct_answers": player["correct_answers"],
                "accuracy": round(player["correct_answers"] / player["questions_answered"] * 100, 2) if player["questions_answered"] > 0 else 0
            },
            "base_reward": base_reward,
            "bonus": bonus,
            "total_reward": total_reward
        }