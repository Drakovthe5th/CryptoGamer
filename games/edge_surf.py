from .base_game import BaseGame

class EdgeSurf(BaseGame):
    def __init__(self):
        super().__init__("edge_surf")
        self.max_score_per_second = 120
        
    def get_init_data(self, user_id):
        return {
            **super().get_init_data(user_id),
            "instructions": "Surf the waves and avoid obstacles to earn TON!",
            "controls": {
                "up": ["Up Arrow", "W"],
                "down": ["Down Arrow", "S"],
                "left": ["Left Arrow", "A"],
                "right": ["Right Arrow", "D"]
            }
        }
    
    def handle_action(self, user_id, action, data):
        # Similar implementation to TRexRunner
        pass