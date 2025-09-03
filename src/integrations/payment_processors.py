import stripe
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime
import json

from config import Config
from src.database.mongo import get_user_data, update_user_data, get_stars_transactions, update_stars_transaction

logger = logging.getLogger(__name__)

class PaymentProcessor:
    def __init__(self):
        self.stripe_initialized = False
        self.initialize_stripe()
        
    def initialize_stripe(self):
        """Initialize Stripe with API key"""
        try:
            stripe.api_key = Config.STRIPE_API_KEY
            self.stripe_initialized = True
            logger.info("Stripe initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Stripe: {str(e)}")
            self.stripe_initialized = False

    # Telegram Stars Payment Methods
    def create_stars_invoice(self, user_id: int, product_id: str, title: str, 
                           description: str, price_stars: int, photo_url: str = None) -> Dict:
        """
        Create a Telegram Stars invoice for digital goods
        """
        payload = {
            'user_id': user_id,
            'product_id': product_id,
            'title': title,
            'description': description,
            'payload': f"purchase:{user_id}:{product_id}",
            'currency': 'XTR',
            'prices': [{'label': title, 'amount': price_stars}],
            'provider_token': Config.TELEGRAM_STARS_PROVIDER_TOKEN,
            'start_parameter': f'buy_{product_id}',
            'need_email': False,
            'need_phone_number': False,
            'need_shipping_address': False,
            'is_flexible': False,
            'send_email_to_provider': False,
            'send_phone_number_to_provider': False
        }
        
        if photo_url:
            payload['photo_url'] = photo_url
            
        return payload

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def verify_stars_payment(self, init_data: str, credentials: dict) -> bool:
        """
        Verify Telegram Stars payment using initData and credentials
        """
        try:
            # Validate Telegram initData
            if not self.validate_telegram_init_data(init_data):
                return False
                
            # Verify payment credentials with Telegram API
            response = requests.post(
                f'https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/validateStarsPayment',
                json={
                    'init_data': init_data,
                    'credentials': credentials
                },
                timeout=10
            )
            
            return response.json().get('ok', False)
            
        except Exception as e:
            logger.error(f"Stars payment verification failed: {str(e)}")
            return False

    def process_stars_purchase(self, user_id: int, credentials: dict, product_id: str) -> Dict:
        """
        Process a Telegram Stars purchase
        """
        try:
            # Verify payment
            if not self.verify_stars_payment(credentials.get('init_data'), credentials):
                return {'success': False, 'error': 'Payment verification failed'}
            
            # Get product details
            product = Config.IN_GAME_ITEMS.get(product_id)
            if not product:
                return {'success': False, 'error': 'Invalid product'}
            
            # Grant product benefits to user
            from src.database.mongo import grant_product_access
            success = grant_product_access(user_id, product_id, product['effect'])
            
            if success:
                # Record transaction
                transaction_data = {
                    'transaction_id': credentials.get('charge_id', f"stars_{datetime.now().timestamp()}"),
                    'product_id': product_id,
                    'amount': product.get('price_stars', 0),
                    'currency': 'XTR',
                    'status': 'completed',
                    'timestamp': datetime.utcnow(),
                    'details': {
                        'product_name': product.get('name', product_id),
                        'user_id': user_id
                    }
                }
                
                # Update user's stars balance and transaction history
                user_data = get_user_data(user_id)
                if user_data:
                    current_stars = user_data.get('telegram_stars', 0)
                    update_user_data(user_id, {
                        'telegram_stars': current_stars - product.get('price_stars', 0),
                        'stars_transactions': user_data.get('stars_transactions', []) + [transaction_data]
                    })
                
                return {
                    'success': True,
                    'product_id': product_id,
                    'product_name': product.get('name', product_id),
                    'stars_spent': product.get('price_stars', 0)
                }
            else:
                return {'success': False, 'error': 'Failed to grant product access'}
                
        except Exception as e:
            logger.error(f"Stars purchase processing failed: {str(e)}")
            return {'success': False, 'error': 'Internal processing error'}

    # Bot Payments API Methods (Physical Goods)
    def create_bot_invoice(self, user_id: int, items: List[Dict], shipping_options: List[Dict] = None,
                         currency: str = 'USD', need_shipping: bool = False) -> Dict:
        """
        Create an invoice for physical goods using Bot Payments API
        """
        payload = {
            'chat_id': user_id,
            'title': 'Purchase Invoice',
            'description': 'Your order details',
            'payload': f"physical_goods:{user_id}:{datetime.now().timestamp()}",
            'provider_token': Config.TELEGRAM_PAYMENTS_PROVIDER_TOKEN,
            'currency': currency,
            'prices': items,
            'max_tip_amount': 1000 if Config.ALLOW_TIPS else 0,
            'suggested_tip_amounts': [100, 200, 500, 1000] if Config.ALLOW_TIPS else [],
            'start_parameter': 'purchase',
            'need_shipping_address': need_shipping,
            'is_flexible': need_shipping and bool(shipping_options),
            'send_email_to_provider': False,
            'send_phone_number_to_provider': False
        }
        
        if shipping_options:
            payload['shipping_options'] = shipping_options
            
        return payload

    def process_bot_payment(self, update, context) -> bool:
        """
        Process Bot API payment for physical goods
        """
        try:
            query = update.pre_checkout_query
            # Validate the order
            if self.validate_order(query.invoice_payload):
                # Confirm order is available
                query.answer(ok=True)
                return True
            else:
                query.answer(ok=False, error_message="Sorry, this item is no longer available")
                return False
        except Exception as e:
            logger.error(f"Bot payment processing failed: {str(e)}")
            return False

    def complete_bot_payment(self, update, context) -> bool:
        """
        Complete Bot API payment and process order
        """
        try:
            message = update.message
            # Process successful payment
            successful_payment = message.successful_payment
            
            # Extract order details from invoice_payload
            order_details = self.parse_invoice_payload(successful_payment.invoice_payload)
            
            # Update order status and process shipping
            self.fulfill_order(order_details, successful_payment)
            
            logger.info(f"Payment completed for order: {order_details['order_id']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to complete payment: {str(e)}")
            return False

    # Multi-Currency Support (TON/USDT)
    def create_crypto_invoice(self, user_id: int, amount: float, currency: str, 
                            product_id: str = None) -> Dict:
        """
        Create invoice for crypto payments (TON/USDT)
        """
        supported_currencies = ['TON', 'USDT']
        
        if currency not in supported_currencies:
            raise ValueError(f"Unsupported currency. Available: {supported_currencies}")
        
        # Generate unique payment address or reference
        payment_reference = f"crypto_{user_id}_{datetime.now().timestamp()}"
        
        invoice_data = {
            'user_id': user_id,
            'amount': amount,
            'currency': currency,
            'payment_reference': payment_reference,
            'status': 'pending',
            'created_at': datetime.utcnow(),
            'expires_at': datetime.utcnow().timestamp() + 3600,  # 1 hour expiration
            'product_id': product_id
        }
        
        # Store invoice in database
        from src.database.mongo import get_db
        db = get_db()
        db.crypto_invoices.insert_one(invoice_data)
        
        return {
            'payment_reference': payment_reference,
            'amount': amount,
            'currency': currency,
            'payment_address': self.get_payment_address(currency),
            'expires_at': invoice_data['expires_at']
        }

    def verify_crypto_payment(self, payment_reference: str, currency: str) -> Dict:
        """
        Verify crypto payment using blockchain explorer
        """
        try:
            # Check payment status from blockchain
            payment_status = self.check_blockchain_transaction(payment_reference, currency)
            
            if payment_status['confirmed']:
                # Update invoice status
                from src.database.mongo import get_db
                db = get_db()
                db.crypto_invoices.update_one(
                    {'payment_reference': payment_reference},
                    {'$set': {'status': 'completed', 'confirmed_at': datetime.utcnow()}}
                )
                
                # Process the order
                invoice = db.crypto_invoices.find_one({'payment_reference': payment_reference})
                if invoice and invoice.get('product_id'):
                    self.process_crypto_purchase(invoice['user_id'], invoice['product_id'])
            
            return payment_status
            
        except Exception as e:
            logger.error(f"Crypto payment verification failed: {str(e)}")
            return {'confirmed': False, 'error': str(e)}

    # Utility Methods
    def validate_telegram_init_data(self, init_data: str) -> bool:
        """
        Validate Telegram WebApp initData signature
        """
        # Implementation depends on Telegram's validation method
        # This is a placeholder - implement proper validation
        return True

    def validate_order(self, invoice_payload: str) -> bool:
        """
        Validate if order is still available
        """
        # Implement order validation logic
        return True

    def parse_invoice_payload(self, payload: str) -> Dict:
        """
        Parse invoice payload to extract order details
        """
        try:
            # Example payload format: "order:user_id:product_id:timestamp"
            parts = payload.split(':')
            return {
                'type': parts[0],
                'user_id': int(parts[1]),
                'product_id': parts[2],
                'timestamp': parts[3] if len(parts) > 3 else None
            }
        except:
            return {'raw_payload': payload}

    def fulfill_order(self, order_details: Dict, payment_info: Dict) -> bool:
        """
        Process order fulfillment after successful payment
        """
        # Implement order processing logic
        return True

    def get_payment_address(self, currency: str) -> str:
        """
        Get payment address for specific cryptocurrency
        """
        if currency == 'TON':
            return Config.TON_PAYMENT_ADDRESS
        elif currency == 'USDT':
            return Config.USDT_PAYMENT_ADDRESS
        else:
            raise ValueError(f"Unsupported currency: {currency}")

    def check_blockchain_transaction(self, reference: str, currency: str) -> Dict:
        """
        Check blockchain for transaction confirmation
        """
        # Implement blockchain transaction checking
        # This would typically use a blockchain explorer API
        return {
            'confirmed': False,
            'confirmations': 0,
            'transaction_hash': None
        }

    def process_crypto_purchase(self, user_id: int, product_id: str) -> bool:
        """
        Process purchase after crypto payment confirmation
        """
        # Implement product delivery logic
        return True

    # Refund Methods
    def refund_stars_payment(self, user_id: int, charge_id: str) -> Dict:
        """
        Refund a Telegram Stars payment
        """
        try:
            # Implementation would use Telegram API for refunds
            response = requests.post(
                f'https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/refundStarsPayment',
                json={
                    'user_id': user_id,
                    'charge_id': charge_id
                }
            )
            
            if response.json().get('ok', False):
                # Update transaction status
                update_stars_transaction(user_id, charge_id, 'refunded')
                return {'success': True, 'refund_id': response.json().get('refund_id')}
            else:
                return {'success': False, 'error': 'Refund failed'}
                
        except Exception as e:
            logger.error(f"Stars refund failed: {str(e)}")
            return {'success': False, 'error': str(e)}

# Global payment processor instance
payment_processor = PaymentProcessor()