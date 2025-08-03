import logging
import os

def setup_logger():
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=log_level
    )
    
    # Add ad performance logger
    ad_logger = logging.getLogger('ad_performance')
    ad_handler = logging.FileHandler('ad_performance.log')
    ad_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    ad_logger.addHandler(ad_handler)
    ad_logger.setLevel(logging.INFO)
    
    return logging.getLogger(__name__)

# Initialize logger
logger = setup_logger()