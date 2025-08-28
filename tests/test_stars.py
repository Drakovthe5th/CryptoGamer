# scripts/test_stars.py
import asyncio
from src.integrations.stars import create_stars_invoice, handle_stars_webhook
from src.database.mongo import get_stars_transactions

async def test_stars_integration():
    """Test Stars payment integration"""
    print("Testing Stars integration...")
    
    # Test invoice creation
    invoice = await create_stars_invoice(
        user_id=12345,
        product_id="test_product",
        title="Test Product",
        description="A test product for Stars integration",
        price_stars=100
    )
    
    if invoice:
        print("✅ Invoice creation successful")
        print(f"Invoice URL: {invoice.get('url')}")
    else:
        print("❌ Invoice creation failed")
        return False
    
    # Test webhook handling (simulate successful payment)
    webhook_payload = {
        'event_type': 'payment.succeeded',
        'user_id': 12345,
        'stars_amount': 100,
        'transaction_id': 'test_tx_123'
    }
    
    result = await handle_stars_webhook(webhook_payload)
    if result.get('status') == 'success':
        print("✅ Webhook handling successful")
    else:
        print("❌ Webhook handling failed")
        return False
    
    # Check transaction history
    transactions = get_stars_transactions(12345)
    if transactions and len(transactions) > 0:
        print("✅ Transaction recording successful")
        print(f"Latest transaction: {transactions[0]}")
    else:
        print("❌ Transaction recording failed")
        return False
    
    print("All tests passed! ✅")
    return True

if __name__ == "__main__":
    asyncio.run(test_stars_integration())