import schedule
import time
import requests
from src.integrations.nano import get_wallet_address
from config import config
import logging

logger = logging.getLogger(__name__)

def claim_from_faucets():
    try:
        address = get_wallet_address()
        if not address:
            logger.error("Skipping faucet claims: No wallet address available")
            return
            
        faucets = [
            f"https://faucet.zenofnano.com/claim?address={address}",
            f"https://nanodrop.io/claim.php?address={address}",
            f"https://free-nano.com/claim.php?address={address}"
        ]
        
        for url in faucets:
            try:
                response = requests.get(url, timeout=15)
                if response.status_code == 200:
                    logger.info(f"Claimed from {url}")
                else:
                    logger.warning(f"Faucet returned {response.status_code}: {url}")
            except Exception as e:
                logger.error(f"Faucet claim failed ({url}): {str(e)}")
    except Exception as e:
        logger.error(f"Error in faucet claim process: {str(e)}")

def start_faucet_scheduler():
    try:
        # Run immediately on start
        claim_from_faucets()
        
        # Schedule regular claims
        schedule.every(4).hours.do(claim_from_faucets)
        
        while True:
            schedule.run_pending()
            time.sleep(60)
    except Exception as e:
        logger.error(f"Faucet scheduler failed: {str(e)}")