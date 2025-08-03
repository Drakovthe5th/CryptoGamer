import unittest
from unittest.mock import patch, MagicMock
from src.features.quests import get_active_quests, complete_quest

class TestQuests(unittest.TestCase):
    
    @patch('src.database.firebase.quests_ref')
    def test_get_active_quests(self, mock_quests_ref):
        # Mock Firestore response
        mock_quest1 = MagicMock()
        mock_quest1.to_dict.return_value = {'title': 'Quest 1', 'active': True}
        
        mock_quest2 = MagicMock()
        mock_quest2.to_dict.return_value = {'title': 'Quest 2', 'active': True}
        
        mock_quests_ref.where.return_value.stream.return_value = [mock_quest1, mock_quest2]
        
        quests = list(get_active_quests())
        self.assertEqual(len(quests), 2)
        self.assertEqual(quests[0].to_dict()['title'], 'Quest 1')
    
    @patch('src.database.firebase.quests_ref')
    @patch('src.database.firebase.update_balance')
    @patch('src.database.firebase.update_leaderboard_points')
    @patch('src.database.firebase.get_user_ref')
    def test_complete_quest(self, mock_get_user_ref, mock_update_points, mock_update_balance, mock_quests_ref):
        # Mock quest data
        mock_quest_doc = MagicMock()
        mock_quest_doc.exists = True
        mock_quest_doc.to_dict.return_value = {
            'reward_xno': 0.5,
            'reward_points': 20
        }
        mock_quests_ref.document.return_value.get.return_value = mock_quest_doc
        
        # Mock user reference
        mock_user_ref = MagicMock()
        mock_get_user_ref.return_value = mock_user_ref
        
        result = complete_quest(123, 'quest1')
        self.assertTrue(result)
        
        # Verify rewards were awarded
        mock_update_balance.assert_called_with(123, 0.5)
        mock_update_points.assert_called_with(123, 20)
        
        # Verify quest completion was recorded
        mock_quests_ref.document.return_value.update.assert_called_with({
            'completions': unittest.mock.ANY  # Firestore Increment
        })
        mock_user_ref.update.assert_called_with({
            'completed_quests.quest1': unittest.mock.ANY  # SERVER_TIMESTAMP
        })