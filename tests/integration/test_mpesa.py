import unittest
from unittest.mock import patch
from src.integrations.mpesa import process_mpesa_withdrawal

class TestMpesaIntegration(unittest.TestCase):
    
    @patch('src.integrations.mpesa.initialize_mpesa')
    def test_successful_withdrawal(self, mock_init):
        # Mock successful response
        mock_mpesa = mock_init.return_value
        mock_mpesa.customer_to_bussiness.return_value = {
            'ResponseCode': '0',
            'CheckoutRequestID': 'test123'
        }
        
        response = process_mpesa_withdrawal('254712345678', 10)
        self.assertEqual(response['ResponseCode'], '0')
        self.assertIn('CheckoutRequestID', response)

    @patch('src.integrations.mpesa.initialize_mpesa')
    def test_failed_withdrawal(self, mock_init):
        # Mock failed response
        mock_mpesa = mock_init.return_value
        mock_mpesa.customer_to_bussiness.return_value = {
            'ResponseCode': '1',
            'errorMessage': 'Insufficient funds'
        }
        
        response = process_mpesa_withdrawal('254712345678', 10)
        self.assertEqual(response['ResponseCode'], '1')
        self.assertIn('errorMessage', response)