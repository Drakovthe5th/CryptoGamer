import stripe
from config import Config

def initialize_stripe():
    stripe.api_key = Config.STRIPE_API_KEY

def create_payment_intent(amount: float, currency='usd'):
    return stripe.PaymentIntent.create(
        amount=int(amount * 100),  # Convert to cents
        currency=currency,
        automatic_payment_methods={'enabled': True}
    )