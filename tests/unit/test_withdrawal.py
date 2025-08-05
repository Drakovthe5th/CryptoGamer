import unittest
from unittest.mock import patch, MagicMock
from src.integrations.withdrawal import process_withdrawal

class TestWithdrawals(unittest.TestCase):
    
    @patch('src.database.firebase.db')
    @patch('src.integrations.nano.send_transaction')
    def test_nano_withdrawal_success(self, mock_send, mock_db):
        # Mock successful Nano transaction
        mock_send.return_value = 'tx_hash123'
        
        # Mock Firestore
        mock_withdrawal_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_withdrawal_ref
        
        result = process_withdrawal(123, 'nano', 1.0, {'address': 'nano_123'})
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['tx_id'], 'tx_hash123')
    
    @patch('src.database.firebase.db')
    @patch('src.integrations.mpesa.process_mpesa_withdrawal')
    def test_mpesa_withdrawal_failure(self, mock_mpesa, mock_db):
        # Mock failed M-Pesa transaction
        mock_mpesa.return_value = {
            'ResponseCode': '1',
            'errorMessage': 'Insufficient funds'
        }
        
        result = process_withdrawal(123, 'mpesa', 10.0, {'phone': '254712345678'})
        self.assertEqual(result['status'], 'failed')
        self.assertIn('error', result)
    
    @patch('src.database.firebase.db')
    @patch('src.integrations.paypal.create_payout')
    @patch('src.utils.conversions.usd_to_xno')
    def test_paypal_withdrawal(self, mock_conversion, mock_payout, mock_db):
        # Mock currency conversion
        mock_conversion.return_value = 5.0  # 5 USD equivalent
        
        # Mock successful PayPal payout
        mock_payout.return_value = {
            'status': 'success',
            'payout_batch_id': 'PAY-123'
        }
        
        result = process_withdrawal(123, 'paypal', 1.0, {'email': 'user@example.com'})
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['tx_id'], 'PAY-123')