# src/telegram/config_manager.py
import logging
import json
import asyncio
from datetime import datetime, timedelta
from functools import lru_cache
from src.integrations.telegram import telegram_client
from config import config

logger = logging.getLogger(__name__)

class TelegramConfigManager:
    def __init__(self):
        self.config_cache = None
        self.last_fetch_time = None
        self.cache_duration = 3600  # 1 hour cache
        
    async def get_client_config(self, force_refresh=False):
        """Get Telegram client configuration with caching"""
        # Return cached config if still valid
        if (self.config_cache and not force_refresh and 
            self.last_fetch_time and 
            (datetime.now() - self.last_fetch_time).total_seconds() < self.cache_duration):
            return self.config_cache
            
        try:
            # Try to fetch from Telegram API
            async with telegram_client:
                config_result = await telegram_client(functions.help.GetAppConfigRequest(hash=0))
                
                if isinstance(config_result, types.help.AppConfig):
                    self.config_cache = self._parse_config(config_result.config)
                    self.last_fetch_time = datetime.now()
                    logger.info("Successfully fetched Telegram client config")
                    return self.config_cache
                else:
                    logger.warning("Failed to fetch config, using defaults")
                    return config.TELEGRAM_CLIENT_CONFIG
                    
        except Exception as e:
            logger.error(f"Error fetching Telegram config: {str(e)}")
            # Fall back to default config
            return config.TELEGRAM_CLIENT_CONFIG
            
    def _parse_config(self, json_value):
        """Parse Telegram JSON config into Python dict"""
        try:
            if hasattr(json_value, 'to_dict'):
                return json_value.to_dict()
            elif hasattr(json_value, '__dict__'):
                return json_value.__dict__
            else:
                # Handle raw JSON value
                return json.loads(str(json_value))
        except Exception as e:
            logger.error(f"Error parsing config: {str(e)}")
            return config.TELEGRAM_CLIENT_CONFIG
            
    def get_user_limits(self, user_data):
        """Get appropriate limits based on user's premium status"""
        is_premium = user_data.get('is_premium', False)
        prefix = "premium" if is_premium else "default"
        
        limits = {}
        client_config = self.config_cache or config.TELEGRAM_CLIENT_CONFIG
        
        for key, value in client_config.items():
            if key.endswith(f"_{prefix}"):
                base_key = key.replace(f"_{prefix}", "")
                limits[base_key] = value
            elif not key.endswith(("_default", "_premium")):
                limits[key] = value
                
        return limits
        
    async def handle_config_update(self, update):
        """Handle updateConfig events"""
        if isinstance(update, types.UpdateConfig):
            logger.info("Received config update, refreshing cache")
            await self.get_client_config(force_refresh=True)

# Global instance
config_manager = TelegramConfigManager()