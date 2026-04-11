"""Chatbot implementation for Google Chat.

Sample message from google chat:
{
  "commonEventObject": {
    "userLocale": "en",
    "hostApp": "CHAT",
    "platform": "WEB",
    "timeZone": {
      "id": "Asia/Shanghai",
      "offset": 28800000
    }
  },
  "chat": {
    "user": {
      "name": "users/{12345678}",
      "displayName": "User Name",
      "avatarUrl": "avatar url",
      "email": "user email address",
      "type": "HUMAN",
      "domainId": "domain id"
    },
    "eventTime": "event time",
    "messagePayload": {
      "space": {
        "name": "spaces/{12345678}",
        "type": "DM",
        "singleUserBotDm": true,
        "spaceThreadingState": "THREADED_MESSAGES",
        "spaceType": "DIRECT_MESSAGE",
        "spaceHistoryState": "HISTORY_ON",
        "lastActiveTime": "event time",
        "membershipCount": {
          "joinedDirectHumanUserCount": 1
        },
        "spaceUri": "space uri"
      },
      "message": {
        "name": "spaces/{12345678}/messages/{12345678}",
        "sender": {
          "name": "users/{12345678}",
          "displayName": "User Name",
          "avatarUrl": "avatar url",
          "email": "user email address",
          "type": "HUMAN",
          "domainId": "domain id"
        },
        "createTime": "event time",
        "text": "message text",
        "thread": {
          "name": "spaces/{12345678}/threads/{12345678}",
          "retentionSettings": {
            "state": "PERMANENT"
          }
        },
        "space": {
          "name": "spaces/{12345678}",
          "type": "DM",
          "singleUserBotDm": true,
          "spaceThreadingState": "THREADED_MESSAGES",
          "spaceType": "DIRECT_MESSAGE",
          "spaceHistoryState": "HISTORY_ON",
          "lastActiveTime": "event time",
          "membershipCount": {
            "joinedDirectHumanUserCount": 1
          },
          "spaceUri": "space uri"
        },
        "argumentText": "message text",
        "retentionSettings": {
          "state": "PERMANENT"
        },
        "messageHistoryState": "HISTORY_ON",
        "formattedText": "message text"
      },
      "configCompleteRedirectUri": "config complete redirect uri"
    }
  }
}
"""

import os
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from google.cloud import pubsub_v1
from .chatbot import ChatBot
from . import db
from . import utils

logger = utils.setup_logger(__name__)


class GoogleChatBot(ChatBot):
    """
    Google Chat implementation of the ChatBot using Pub/Sub for receiving messages.
    Currently only supports non-streaming mode for outbound messages.
    """
    def __init__(self, google_chat_config: dict):
        self.google_chat_config = google_chat_config
        self.project_id = google_chat_config.get('google_cloud_project')
        self.subscription_id = google_chat_config.get('google_chat_subscription')
        self.subscriber = None
        self.streaming_pull_future = None
        self.agent = None

    @property
    def user_id(self) -> str:
        return "google_chat_bot"

    def is_stream_off(self, channel_id: str) -> bool:
        return True  # Always non-streaming for now

    async def get_author_name(self, author_id: str) -> str:
        return f"User_{author_id}"

    async def get_system_instructions(self, channel_id: str) -> str:
        return "---BEGIN GOOGLE CHAT INSTRUCTIONS---\nYou are in a Google Chat space.\n---END GOOGLE CHAT INSTRUCTIONS---\n"

    @asynccontextmanager
    async def typing(self, channel_id: str):
        yield

    async def channel_exists(self, channel_id: str) -> bool:
        return True

    async def ensure_thread_for_cronjob(self, channel_id: str, prompt: str, mention_user_id: str, gemini_session_id: str) -> str:
        return channel_id

    async def send_message(self, channel_id: str, content: str):
        logger.info(f"Google Chat [Channel {channel_id}]: {content}")
        
        space_name = channel_id
        if space_name.startswith("gchat:"):
            space_name = space_name[len("gchat:"):]
            
        # space_name might be "spaces/AAAA/threads/BBBB" or "spaces/AAAA"
        parts = space_name.split('/')
        if len(parts) >= 2 and parts[0] == 'spaces':
            base_space = f"spaces/{parts[1]}"
        else:
            base_space = space_name
            
        try:
            import google.auth
            import google.auth.transport.requests
            import requests
            
            credentials, project_id = google.auth.default(
                scopes=['https://www.googleapis.com/auth/chat.messages.create'],
                quota_project_id=self.project_id
            )
            if project_id != self.project_id:
                logger.error(f"Project id mismatch: gchat using {project_id} instead of {self.project_id}")
            auth_request = google.auth.transport.requests.Request()
            credentials.refresh(auth_request)
            
            url = f"https://chat.googleapis.com/v1/{base_space}/messages"
            headers = {
                "Authorization": f"Bearer {credentials.token}",
                "Content-Type": "application/json",
                "X-Goog-User-Project": project_id
            }
            payload = {
                "text": content
            }
            
            # If it's a thread, add thread info to reply in thread
            if '/threads/' in space_name:
                payload["thread"] = {"name": space_name}
                
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code != 200:
                logger.error(f"Failed to send message to Google Chat: {response.text}")
            else:
                logger.info(f"Successfully sent message to Google Chat.")
                
        except Exception as e:
            logger.exception(f"Error sending message to Google Chat: {e}")

    async def stream_start(self, channel_id: str):
        pass

    async def stream_send(self, channel_id: str, chunk: str):
        pass

    async def stream_end(self, channel_id: str, error: str = None):
        pass

    async def update_idle_thread_name(self, channel_id: str, response: str):
        pass

    async def start(self):
        """Start listening to Pub/Sub subscription."""
        logger.info("starting google chat")
        if not self.project_id or not self.subscription_id:
            logger.error("Google Cloud Project ID or Subscription ID missing in config.")
            return

        self.subscriber = pubsub_v1.SubscriberClient()
        subscription_path = self.subscriber.subscription_path(self.project_id, self.subscription_id)

        def callback(message):
            # logger.info(f"Received Pub/Sub message: {message.data}")
            logger.info(message.attributes)
            try:
                data = json.loads(message.data.decode('utf-8'))
                
                # Google Chat events documentation:
                # https://developers.google.com/chat/api/guides/message-formats/events
                chat = data.get('chat', {})
                payload = chat.get('messagePayload', {})
                chat_message = payload.get('message')
                
                if chat_message:
                    space = payload.get('space')
                    thread = chat_message.get('thread')
                    
                    # Use thread name as channel_id for threading
                    if thread and thread.get('name'):
                        channel_id = f"gchat:{thread.get('name')}"
                    elif space and space.get('name'):
                        channel_id = f"gchat:{space.get('name')}"
                    else:
                        channel_id = "gchat:unknown_space"
                        
                    message_id = chat_message.get('name', 'unknown_message')
                    
                    sender = chat_message.get('sender', {})
                    author_id = sender.get('name', 'unknown_user')
                    author_name = sender.get('displayName', 'Unknown User')
                    
                    message_text = chat_message.get('text', '')
                    create_time = chat_message.get('createTime', 'unknown_time')
                    
                    # Format prompt with content, author, and timestamp
                    prompt = f"{message_text}\n--- Message Above From {author_name} <@{author_id}> at {create_time} ---\n"
                    
                    logger.info(f"Inserting message from {author_name} in channel {channel_id}")
                    db.insert_message(channel_id, message_id, author_id, prompt)
                    
                message.ack()
            except Exception as e:
                logger.exception(f"Error processing Pub/Sub message: {e}")
                # message.nack()
                message.ack()

        self.streaming_pull_future = self.subscriber.subscribe(subscription_path, callback=callback)
        if self.agent:
            asyncio.create_task(self.agent.process_pending_messages_loop())
        logger.info(f"Listening for Google Chat messages on {subscription_path}")

    async def stop(self):
        """Stop listening to Pub/Sub subscription."""
        if self.streaming_pull_future:
            self.streaming_pull_future.cancel()
            logger.info("Stopped listening to Pub/Sub subscription.")

    def run(self, token: str = None):
        """Run the bot."""        
        async def main():
            await self.start()
            try:
                while True:
                    await asyncio.sleep(3600)
            except asyncio.CancelledError:
                await self.stop()

        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received, stopping.")
