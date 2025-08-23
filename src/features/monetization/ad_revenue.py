from src.utils.logger import logging

logger = logging.getLogger(__name__)
class AdRevenue:
    def __init__(self, telegram_client):
        self.telegram_client = telegram_client
        self.rates = {
            'monetag': 0.003,
            'a-ads': 0.0012,
            'ad-mob': 0.0025,
            'telegram': 0.005  # Estimated rate for Telegram ads
        }
    
    def record_impression(self, ad_network):
        return self.rates.get(ad_network, 0)
    
    def record_completed_view(self, ad_network):
        return self.rates.get(ad_network, 0) * 1.2
    
    async def get_admin_revenue_stats(self, peer, dark=False):
        """Get ad revenue stats for admin only"""
        try:
            result = await self.telegram_client(
                functions.stats.GetBroadcastRevenueStatsRequest(
                    peer=peer,
                    dark=dark
                )
            )
            return result
        except Exception as e:
            logger.error(f"Failed to get revenue stats: {e}")
            return None
            
    async def get_admin_revenue_transactions(self, peer, offset=0, limit=100):
        """Get revenue transactions for admin only"""
        try:
            result = await self.telegram_client(
                functions.stats.GetBroadcastRevenueTransactionsRequest(
                    peer=peer,
                    offset=offset,
                    limit=limit
                )
            )
            return result
        except Exception as e:
            logger.error(f"Failed to get revenue transactions: {e}")
            return None
            
    async def get_admin_withdrawal_url(self, peer, password):
        """Get withdrawal URL for admin only"""
        try:
            result = await self.telegram_client(
                functions.stats.GetBroadcastRevenueWithdrawalUrlRequest(
                    peer=peer,
                    password=password
                )
            )
            return result
        except Exception as e:
            logger.error(f"Failed to get withdrawal URL: {e}")
            return None