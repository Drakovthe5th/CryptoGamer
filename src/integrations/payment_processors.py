import stripe
import requests
from config import Config
import logging

logger = logging.getLogger(__name__)

def initialize_stripe():
    stripe.api_key = Config.STRIPE_API_KEY

def create_payment_intent(amount: float, currency='usd'):
    return stripe.PaymentIntent.create(
        amount=int(amount * 100),  # Convert to cents
        currency=currency,
        automatic_payment_methods={'enabled': True}
    )

# Telegram Stars Payment Functions
def create_stars_invoice(user_id: int, product_id: str, title: str, description: str, 
                        price_stars: int, photo_url: str = None):
    """
    Create a Telegram Stars invoice for digital goods
    """
    payload = {
        'user_id': user_id,
        'product_id': product_id,
        'title': title,
        'description': description,
        'payload': f"purchase:{user_id}:{product_id}".encode(),
        'currency': 'XTR',  # Telegram Stars currency code
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

def verify_stars_payment(init_data: str, credentials: dict) -> bool:
    """
    Verify Telegram Stars payment using initData and credentials
    """
    try:
        # Validate Telegram initData
        if not validate_telegram_init_data(init_data):
            return False
            
        # Verify payment credentials with Telegram API
        response = requests.post(
            'https://api.telegram.org/bot{}/validateStarsPayment'.format(Config.TELEGRAM_TOKEN),
            json={
                'init_data': init_data,
                'credentials': credentials
            }
        )
        
        return response.json().get('ok', False)
        
    except Exception as e:
        logger.error(f"Stars payment verification failed: {str(e)}")
        return False

def process_stars_purchase(user_id: int, credentials: dict, product_id: str) -> dict:
    """
    Process a Telegram Stars purchase
    """
    try:
        # Verify payment
        if not verify_stars_payment(credentials.get('init_data'), credentials):
            return {'success': False, 'error': 'Payment verification failed'}
        
        # Get product details
        product = Config.IN_GAME_ITEMS.get(product_id)
        if not product:
            return {'success': False, 'error': 'Invalid product'}
        
        # Grant product benefits to user
        from src.database.mongo import grant_product_access
        success = grant_product_access(user_id, product_id, product['effect'])
        
        if success:
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
    
def create_stars_invoice_for_gift(user_id: int, gift_id: str, gift_data: dict):
    """
    Create a Telegram Stars invoice for gift purchase
    """
    return {
        'user_id': user_id,
        'product_id': f"gift_{gift_id}",
        'title': f"🎁 {gift_data['name']}",
        'description': f"Send this gift to a friend!",
        'payload': f"gift:{user_id}:{gift_id}".encode(),
        'currency': 'XTR',
        'prices': [{'label': 'Gift', 'amount': gift_data['stars']}],
        'provider_token': Config.TELEGRAM_STARS_PROVIDER_TOKEN,
        'photo_url': gift_data.get('image_url')
    }

def create_stars_invoice_for_giveaway(user_id: int, giveaway_type: str, details: dict):
    """
    Create a Telegram Stars invoice for giveaway
    """
    if giveaway_type == 'premium':
        title = f"🎉 {details['users_count']}x Premium Giveaway"
        description = f"{details['months']} months Telegram Premium for {details['users_count']} winners"
    else:
        title = f"⭐ {details['stars_amount']} Stars Giveaway"
        description = f"{details['winners_count']} winners, {details['per_user_stars']} stars each"
    
    return {
        'user_id': user_id,
        'product_id': f"giveaway_{giveaway_type}_{int(datetime.now().timestamp())}",
        'title': title,
        'description': description,
        'payload': f"giveaway:{user_id}:{giveaway_type}".encode(),
        'currency': 'XTR',
        'prices': [{'label': 'Giveaway', 'amount': details['stars_amount'] if giveaway_type == 'stars' else details['premium_cost']}],
        'provider_token': Config.TELEGRAM_STARS_PROVIDER_TOKEN
    }