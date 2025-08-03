import unittest
from unittest.mock import patch, MagicMock
from src.features.leaderboard import get_leaderboard, get_user_rank

class TestLeaderboard(unittest.TestCase):
    
    @patch('src.database.firebase.users_ref')
    def test_get_leaderboard(self, mock_users_ref):
        # Mock Firestore response
        mock_user1 = MagicMock()
        mock_user1.to_dict.return_value = {'username': 'User1', 'points': 100}
        
        mock_user2 = MagicMock()
        mock_user2.to_dict.return_value = {'username': 'User2', 'points': 90}
        
        mock_users_ref.order_by.return_value.limit.return_value.stream.return_value = [mock_user1, mock_user2]
        
        leaderboard = get_leaderboard(2)
        self.assertEqual(len(leaderboard), 2)
        self.assertEqual(leaderboard[0]['username'], 'User1')
        self.assertEqual(leaderboard[0]['points'], 100)
    
    @patch('src.database.firebase.users_ref')
    def test_get_user_rank(self, mock_users_ref):
        # Mock Firestore response
        mock_user1 = MagicMock()
        mock_user1.id = '123'
        mock_user1.to_dict.return_value = {'points': 100}
        
        mock_user2 = MagicMock()
        mock_user2.id = '456'
        mock_user2.to_dict.return_value = {'points': 90}
        
        mock_user3 = MagicMock()
        mock_user3.id = '789'
        mock_user3.to_dict.return_value = {'points': 80}
        
        mock_users_ref.order_by.return_value.stream.return_value = [mock_user1, mock_user2, mock_user3]
        
        self.assertEqual(get_user_rank(456), 2)
        self.assertEqual(get_user_rank(999), -1)