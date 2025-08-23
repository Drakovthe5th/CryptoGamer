from telethon import TelegramClient, functions, types
from telethon.sessions import StringSession
import requests
import logging
from config import config
from src.features.quests import validate_wallet

logger = logging.getLogger(__name__)



class TelegramIntegration:
    def __init__(self):
        self.client = None
        self.session_string = config.TELEGRAM_SESSION_STRING
        self.api_id = config.TELEGRAM_API_ID
        self.api_hash = config.TELEGRAM_API_HASH
        
    async def initialize(self):
        """Initialize Telegram client"""
        try:
            self.client = TelegramClient(
                StringSession(self.session_string),
                self.api_id,
                self.api_hash
            )
            await self.client.start()
            logger.info("Telegram client initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Telegram client: {str(e)}")
            return False
            
    async def get_app_config(self, hash=0):
        """Get Telegram client configuration"""
        try:
            if not self.client:
                await self.initialize()
                
            result = await self.client(functions.help.GetAppConfigRequest(hash=hash))
            return result
        except Exception as e:
            logger.error(f"Error getting app config: {str(e)}")
            return None
            
    async def dismiss_suggestion(self, peer, suggestion):
        """Dismiss a suggestion"""
        try:
            if not self.client:
                await self.initialize()
                
            result = await self.client(
                functions.help.DismissSuggestionRequest(
                    peer=peer,
                    suggestion=suggestion
                )
            )
            return result
        except Exception as e:
            logger.error(f"Error dismissing suggestion: {str(e)}")
            return False
            
    async def close(self):
        """Close Telegram client"""
        if self.client:
            await self.client.disconnect()

    def send_telegram_message(user_id: int, message: str) -> bool:
        from src.database.mongo import get_db  # Add this line
        """Send message to user via Telegram"""
        try:
            # Get Telegram chat ID from database
            db = get_user_data()
            user_ref = db.collection('users').document(str(user_id))
            user_doc = user_ref.get()
            
            if not user_doc.exists:
                logger.warning(f"No user record found for {user_id}")
                return False
                
            user_data = user_doc.to_dict()
            chat_id = user_data.get('telegram_chat_id')
            
            if not chat_id:
                logger.warning(f"No Telegram chat ID for user {user_id}")
                return False
                
            url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info(f"Telegram message sent to user {user_id}")
                return True
            else:
                logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Telegram message exception: {e}")
            return False
        
    async def handle_webapp_data(data):
        if data['type'] == 'connect_wallet':
            from src.utils.validators import validate_ton_address
            from src.database.mongo import connect_wallet as save_wallet
            
            user_id = data['user_id']
            wallet_address = data['address']
            
            if validate_ton_address(wallet_address):
                if save_wallet(user_id, wallet_address):
                    return "Wallet connected successfully!"
                return "Database error"
            return "Invalid wallet address"
        
        return "Unknown action"

    # Add these methods to the TelegramIntegration class
    async def create_affiliate_program(self, commission_permille, duration_months=None):
        """Create or update affiliate program for our bot"""
        try:
            if not self.client:
                await self.initialize()
                
            # Get our bot's user ID
            me = await self.client.get_me()
            
            result = await self.client(
                functions.bots.UpdateStarRefProgramRequest(
                    bot=types.InputUser(user_id=me.id, access_hash=me.access_hash),
                    commission_permille=commission_permille,
                    duration_months=duration_months
                )
            )
            return result
        except Exception as e:
            logger.error(f"Error creating affiliate program: {str(e)}")
            return None

    async def join_affiliate_program(self, bot_username, peer_type="user"):
        """Join another bot's affiliate program"""
        try:
            if not self.client:
                await self.initialize()
                
            # Resolve the bot username
            bot = await self.client.get_entity(bot_username)
            
            # Determine peer type (user, bot, or channel)
            if peer_type == "user":
                peer = types.InputPeerSelf()
            elif peer_type == "bot":
                # Get one of our own bots
                admined_bots = await self.client(functions.bots.GetAdminedBotsRequest())
                if admined_bots:
                    peer = admined_bots[0]
                else:
                    return None
            elif peer_type == "channel":
                # Get one of our channels with post rights
                channels = await self.client(functions.channels.GetAdminedPublicChannelsRequest())
                for channel in channels:
                    if getattr(channel, 'post_messages', False):
                        peer = channel
                        break
                else:
                    return None
            
            result = await self.client(
                functions.payments.ConnectStarRefBotRequest(
                    peer=peer,
                    bot=types.InputUser(user_id=bot.id, access_hash=bot.access_hash)
                )
            )
            return result
        except Exception as e:
            logger.error(f"Error joining affiliate program: {str(e)}")
            return None

    async def get_affiliate_stats(self):
        """Get affiliate program statistics"""
        try:
            if not self.client:
                await self.initialize()
                
            # Get our own affiliate programs
            result = await self.client(
                functions.payments.GetConnectedStarRefBotsRequest(
                    peer=types.InputPeerSelf()
                )
            )
            return result
        except Exception as e:
            logger.error(f"Error getting affiliate stats: {str(e)}")
            return None

    async def connect_wallet(update, context):
        user_id = update.effective_user.id
        wallet_address = update.message.text.strip()
        
        if not validate_wallet(wallet_address):
            return "Invalid wallet address"
        
        user = get_user_data(user_id)
        user.wallet_address = wallet_address
        user.save()
        return "✅ Wallet connected successfully!"
    
        # Add these methods to the TelegramIntegration class
    async def create_invite_link(self, channel_username, expire_date=None, usage_limit=None, title=None):
        """Create an invite link for a channel"""
        try:
            if not self.client:
                await self.initialize()
                
            # Resolve the channel
            channel = await self.client.get_entity(channel_username)
            
            result = await self.client(
                functions.messages.ExportChatInviteRequest(
                    peer=channel,
                    expire_date=expire_date,
                    usage_limit=usage_limit,
                    title=title
                )
            )
            return result
        except Exception as e:
            logger.error(f"Error creating invite link: {str(e)}")
            return None

    async def get_invite_links(self, channel_username, revoked=False):
        """Get invite links for a channel"""
        try:
            if not self.client:
                await self.initialize()
                
            # Resolve the channel
            channel = await self.client.get_entity(channel_username)
            
            result = await self.client(
                functions.messages.GetExportedChatInvitesRequest(
                    peer=channel,
                    revoked=revoked,
                    limit=50
                )
            )
            return result
        except Exception as e:
            logger.error(f"Error getting invite links: {str(e)}")
            return None
        
    async def get_attach_menu_bots(self, hash: int = 0):
        """Get available attachment menu bots"""
        try:
            if not self.client:
                await self.initialize()
                
            result = await self.client(
                functions.messages.GetAttachMenuBotsRequest(
                    hash=hash
                )
            )
            
            if isinstance(result, types.AttachMenuBots):
                return {
                    'hash': result.hash,
                    'bots': [bot.to_dict() for bot in result.bots],
                    'users': [user.to_dict() for user in result.users]
                }
            else:
                return {'not_modified': True}
                
        except Exception as e:
            logger.error(f"Error getting attach menu bots: {str(e)}")
            return None

    async def get_attach_menu_bot(self, bot_id: int):
        """Get specific attachment menu bot info"""
        try:
            if not self.client:
                await self.initialize()
                
            # Create input user
            bot_entity = await self.client.get_entity(bot_id)
            
            result = await self.client(
                functions.messages.GetAttachMenuBotRequest(
                    bot=types.InputUser(
                        user_id=bot_entity.id,
                        access_hash=bot_entity.access_hash
                    )
                )
            )
            
            return result.to_dict()
            
        except Exception as e:
            logger.error(f"Error getting attach menu bot: {str(e)}")
            return None

# Global instance
telegram_client = TelegramIntegration()