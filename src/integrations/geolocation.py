import logging
from typing import Dict, List, Optional
from flask import request, jsonify
from src.database import mongo as db
from src.utils import security
from src.telegram import tonclient

logger = logging.getLogger(__name__)

class GeolocationManager:
    def __init__(self):
        self.active_locations = {}  # user_id -> location_data

    async def get_nearby_users_and_chats(self, user_id: int, geo_point: Dict, background: bool = False, 
                                        self_expires: Optional[int] = None) -> Dict:
        """
        Fetch nearby users and geogroups using Telegram's contacts.getLocated
        """
        try:
            # Convert to Telegram API format
            input_geo_point = {
                '_': 'inputGeoPoint',
                'lat': geo_point['lat'],
                'long': geo_point['long'],
                'accuracy_radius': geo_point.get('accuracy_radius')
            }

            # Call Telegram API
            result = await tonclient.invoke_method(
                'contacts.getLocated',
                geo_point=input_geo_point,
                background=background,
                self_expires=self_expires
            )

            # Process and store location if self_expires is set
            if self_expires:
                self.active_locations[user_id] = {
                    'geo_point': geo_point,
                    'expires_at': datetime.now() + timedelta(seconds=self_expires)
                }

            return {
                'success': True,
                'data': result
            }

        except Exception as e:
            logger.error(f"Error fetching nearby users: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def create_geogroup(self, user_id: int, title: str, about: str, 
                             geo_point: Dict, address: str) -> Dict:
        """
        Create a location-based group using channels.createChannel
        """
        try:
            input_geo_point = {
                '_': 'inputGeoPoint',
                'lat': geo_point['lat'],
                'long': geo_point['long'],
                'accuracy_radius': geo_point.get('accuracy_radius')
            }

            result = await tonclient.invoke_method(
                'channels.createChannel',
                title=title,
                about=about,
                geo_point=input_geo_point,
                address=address,
                megagroup=True
            )

            return {
                'success': True,
                'channel': result
            }

        except Exception as e:
            logger.error(f"Error creating geogroup: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def update_live_location(self, user_id: int, chat_id: int, message_id: int, 
                                  geo_point: Dict, heading: Optional[int] = None,
                                  period: int = 3600) -> Dict:
        """
        Update live location message
        """
        try:
            input_geo_point = {
                '_': 'inputGeoPoint',
                'lat': geo_point['lat'],
                'long': geo_point['long'],
                'accuracy_radius': geo_point.get('accuracy_radius')
            }

            input_media = {
                '_': 'inputMediaGeoLive',
                'geo_point': input_geo_point,
                'heading': heading,
                'period': period
            }

            result = await tonclient.invoke_method(
                'messages.editMessage',
                peer={'_': 'inputPeerChat', 'chat_id': chat_id},
                id=message_id,
                media=input_media
            )

            return {
                'success': True,
                'updated_message': result
            }

        except Exception as e:
            logger.error(f"Error updating live location: {str(e)}")
            return {'success': False, 'error': str(e)}

    async def stop_live_location(self, user_id: int, chat_id: int, message_id: int) -> Dict:
        """
        Stop sharing live location
        """
        try:
            input_media = {
                '_': 'inputMediaGeoLive',
                'stopped': True,
                'geo_point': {'_': 'inputGeoPointEmpty'}
            }

            result = await tonclient.invoke_method(
                'messages.editMessage',
                peer={'_': 'inputPeerChat', 'chat_id': chat_id},
                id=message_id,
                media=input_media
            )

            return {
                'success': True,
                'stopped_message': result
            }

        except Exception as e:
            logger.error(f"Error stopping live location: {str(e)}")
            return {'success': False, 'error': str(e)}

# Initialize geolocation manager
geo_manager = GeolocationManager()