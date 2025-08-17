import os
import time
import threading
import logging
import requests
from datetime import datetime
from config import config
from src.database.firebase import otc_deals_ref, update_user, db
from src.integrations.mpesa import process_mpesa_payment
from src.integrations.paypal import process_paypal_payment
from src.integrations.banking import process_bank_transfer
from src.utils.conversions import game_coins_to_ton

logger = logging.getLogger(__name__)

otc_bp = Blueprint('otc', __name__, url_prefix='/api/otc')

@otc_bp.route('/convert/gc-to-ton', methods=['POST'])
def convert_gc_to_ton():
    try:
        data = request.get_json()
        gc_amount = float(data['gc_amount'])
        
        # Convert using the standard rate
        ton_amount = game_coins_to_ton(gc_amount)
        
        return jsonify({
            'success': True,
            'ton_amount': ton_amount,
            'conversion_rate': 2000  # GC per TON
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
class OTCDesk:
    def __init__(self):
        self.buy_rates = {}
        self.sell_rates = {}
        self.running = True
        self.update_interval = 300  # 5 minutes
        self.last_rate_update = datetime.min
        self.last_processing = datetime.min

    def update_rates(self):
        """Update exchange rates from API and config"""
        try:
            # Fetch from external API
            response = requests.get("https://api.exchangerate-api.com/v4/latest/TON")
            data = response.json()
            
            # Apply configured rates with external data as fallback
            self.buy_rates = {
                'USD': config.OTC_RATES.get("USD", data.get('rates', {}).get('USD', 5.0)) * 0.98,
                'EUR': config.OTC_RATES.get("EUR", data.get('rates', {}).get('EUR', 4.5)) * 0.98,
                'KES': config.OTC_RATES.get("KES", data.get('rates', {}).get('KES', 700.0)) * 0.98
            }
            
            self.sell_rates = {
                'USD': config.OTC_RATES.get("USD", data.get('rates', {}).get('USD', 5.0)) * 1.02,
                'EUR': config.OTC_RATES.get("EUR", data.get('rates', {}).get('EUR', 4.5)) * 1.02,
                'KES': config.OTC_RATES.get("KES", data.get('rates', {}).get('KES', 700.0)) * 1.02
            }
            
            self.last_rate_update = datetime.now()
            logger.info("OTC rates updated successfully")
        except Exception as e:
            logger.error(f"Failed to update OTC rates: {e}")
            # Fallback to config rates
            self.buy_rates = config.OTC_RATES
            self.sell_rates = {k: v * 1.02 for k, v in config.OTC_RATES.items()}

    def get_buy_rate(self, currency: str) -> float:
        """Get current buy rate for currency"""
        return self.buy_rates.get(currency.upper(), 0.0)
        
    def get_sell_rate(self, currency: str) -> float:
        """Get current sell rate for currency"""
        return self.sell_rates.get(currency.upper(), 0.0)
        
    def calculate_fiat_amount(self, ton_amount: float, currency: str) -> float:
        """Calculate fiat amount from TON"""
        rate = self.get_sell_rate(currency)
        return ton_amount * rate
        
    def calculate_fee(self, fiat_amount: float) -> float:
        """Calculate OTC fee"""
        fee = max(
            fiat_amount * (config.OTC_FEE_PERCENT / 100),
            config.MIN_OTC_FEE
        )
        return round(fee, 2)
        
    def create_otc_deal(self, user_id: int, ton_amount: float, currency: str, method: str) -> str:
        """Create OTC deal in Firestore"""
        try:
            fiat_amount = self.calculate_fiat_amount(ton_amount, currency)
            fee = self.calculate_fee(fiat_amount)
            total = fiat_amount - fee
            
            # Get user payment details
            user_ref = db.collection('users').document(str(user_id))
            user_data = user_ref.get().to_dict()
            payment_details = user_data.get('payment_methods', {}).get(method, {})
            
            deal_data = {
                'user_id': user_id,
                'amount_ton': ton_amount,
                'currency': currency,
                'payment_method': method,
                'rate': self.get_sell_rate(currency),
                'fiat_amount': fiat_amount,
                'fee': fee,
                'total': total,
                'status': 'pending',
                'created_at': datetime.now(),
                'payment_details': payment_details
            }
            
            deal_ref = otc_deals_ref.add(deal_data)
            deal_id = deal_ref[1].id
            logger.info(f"Created OTC deal {deal_id} for user {user_id}")
            return deal_id
        except Exception as e:
            logger.error(f"Failed to create OTC deal: {e}")
            return None

    def process_pending_deals(self):
        """Process pending OTC deals"""
        try:
            pending_deals = otc_deals_ref.where('status', '==', 'pending').stream()
            for deal in pending_deals:
                deal_data = deal.to_dict()
                
                # Process based on payment method
                method = deal_data['payment_method']
                result = None
                
                if method == 'M-Pesa':
                    result = process_mpesa_payment(
                        deal_data['payment_details']['phone'],
                        deal_data['total'],
                        deal_data['currency']
                    )
                elif method == 'PayPal':
                    result = process_paypal_payment(
                        deal_data['payment_details']['email'],
                        deal_data['total'],
                        deal_data['currency']
                    )
                elif method == 'Bank Transfer':
                    result = process_bank_transfer(
                        deal_data['payment_details'],
                        deal_data['total'],
                        deal_data['currency']
                    )
                
                # Update deal status
                if result and result.get('status') == 'success':
                    otc_deals_ref.document(deal.id).update({
                        'status': 'completed',
                        'completed_at': datetime.now(),
                        'transaction_id': result.get('transaction_id')
                    })
                    logger.info(f"Processed OTC deal: {deal.id}")
                else:
                    error = result.get('error', 'Unknown error') if result else 'Processing failed'
                    otc_deals_ref.document(deal.id).update({
                        'status': 'failed',
                        'error': error
                    })
                    logger.error(f"Failed to process OTC deal {deal.id}: {error}")
                    
            self.last_processing = datetime.now()
        except Exception as e:
            logger.error(f"OTC deal processing failed: {e}")
    
    def get_quote(self, user_id, currency):
        user_data = get_user_data(user_id)
        game_coins = user_data.get('game_coins', 0)
        return get_otc_quote(game_coins, currency)

    def start(self):
        """Start OTC scheduler"""
        self.update_rates()
        while self.running:
            try:
                # Update rates hourly
                if (datetime.now() - self.last_rate_update).seconds > 3600:
                    self.update_rates()
                
                # Process deals every 5 minutes
                if (datetime.now() - self.last_processing).seconds > 300:
                    self.process_pending_deals()
                
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"OTC scheduler error: {e}")
                time.sleep(60)
            
    def stop(self):
        """Stop OTC scheduler"""
        self.running = False

# Global OTC desk instance
otc_desk = OTCDesk()

def get_otc_quote(game_coins, currency):
    """Generate OTC quote based on game coins"""
    ton_amount = game_coins_to_ton(game_coins)
    rate = buy_rates.get(currency, 0)
    
    if not rate:
        return None
    
    fiat_amount = ton_amount * rate
    fee = calculate_fee(fiat_amount, OTC_FEE_PERCENT, MIN_OTC_FEE)
    total = fiat_amount - fee
    
    return {
        'game_coins': game_coins,
        'amount_ton': ton_amount,
        'currency': currency,
        'rate': rate,
        'fee': fee,
        'total': total
    }

def start_otc_scheduler():
    """Start the OTC desk scheduler"""
    if not config.FEATURE_OTC:
        logger.info("OTC feature disabled")
        return
        
    otc_thread = threading.Thread(target=otc_desk.start)
    otc_thread.daemon = True
    otc_thread.start()
    logger.info("OTC desk scheduler started")