class AdRevenue:
    def __init__(self):
        self.rates = {
            'monetag': 0.003,  # $ per completed view
            'a-ads': 0.0012,    # $ per impression
            'ad-mob': 0.0025
        }
    
    def record_impression(self, ad_network):
        return self.rates.get(ad_network, 0)
    
    def record_completed_view(self, ad_network):
        return self.rates.get(ad_network, 0) * 1.2  # Bonus for completion