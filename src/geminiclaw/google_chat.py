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
        "attachment": [
          {
            "name": "attachment name",
            "contentName": "content name",
            "contentType": "content type",
            "attachmentDataRef": {
              "resourceName": "attachment resource name"
            },
            "thumbnailUri": "thumbnail uri",
            "downloadUri": "download uri",
            "messageMetadata": {
              "name": "message metadata name",
              "sender": "sender",
              "createTime": "create time",
              "updateTime": "update time"
            },
            "source": "source"
          }
        ],
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
import json
import requests
import re
import asyncio
import logging
import mimetypes
import uuid
from contextlib import asynccontextmanager
from google.cloud import pubsub_v1
from .chatbot import ChatBot
import google.auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.http import MediaIoBaseDownload
from . import db
from . import utils

logger = utils.setup_logger(__name__)


class GoogleChatBot(ChatBot):
    """
    Google Chat implementation of the ChatBot using Pub/Sub for receiving messages.
    Currently only supports non-streaming mode for outbound messages.
    """
    def __init__(self, google_chat_config: dict, gemini_config: dict = None):
        self.google_chat_config = google_chat_config
        self.gemini_config = gemini_config or {}
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
        return """
---BEGIN GOOGLE CHAT INSTRUCTIONS---
You are in a Google Chat space.
When sending attachments, use the exact syntax: [attachment: /path/to/file]
---END GOOGLE CHAT INSTRUCTIONS---
"""

    @asynccontextmanager
    async def typing(self, channel_id: str):
        yield

    async def channel_exists(self, channel_id: str) -> bool:
        return True

    async def ensure_thread_for_cronjob(self, channel_id: str, prompt: str, mention_user_id: str, gemini_session_id: str) -> str:
        return channel_id

    async def send_message(self, channel_id: str, content: str):
        logger.info(f"Google Chat [Channel {channel_id}]: {content}")
        
        # Extract attachments
        attachment_pattern = re.compile(r'\[attachment: (.*?)\]')
        attachments = attachment_pattern.findall(content)
        
        # Remove attachment blocks from content
        cleaned_content = attachment_pattern.sub('', content).strip()
        
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
            credentials, project_id = google.auth.default(
                scopes=['https://www.googleapis.com/auth/chat.messages.create'],
                quota_project_id=self.project_id
            )
            
            service = build('chat', 'v1', credentials=credentials)
            
            # Handle attachments
            uploaded_attachments = []
            for file_path in attachments:
                if os.path.exists(file_path):
                    
                    mime_type, _ = mimetypes.guess_type(file_path)
                    if not mime_type:
                        mime_type = 'application/octet-stream'
                        
                    media = MediaFileUpload(file_path, mimetype=mime_type)
                    
                    attachment_uploaded = service.media().upload(
                        parent=base_space,
                        body={'filename': os.path.basename(file_path)},
                        media_body=media
                    ).execute()
                    
                    uploaded_attachments.append(attachment_uploaded)
                else:
                    logger.warning(f"Attachment file not found: {file_path}")
            
            # Create message payload
            body = {
                'text': cleaned_content
            }
            if uploaded_attachments:
                body['attachment'] = uploaded_attachments
                
            # If it's a thread, add thread info to reply in thread
            if '/threads/' in space_name:
                body["thread"] = {"name": space_name}
                
            result = service.spaces().messages().create(
                parent=base_space,
                body=body,
                messageReplyOption='REPLY_MESSAGE_OR_FAIL'
            ).execute()
            logger.info(f"Successfully sent message via Discovery API: {result.get('name')}")

        except Exception as e:
            logger.exception(f"Error sending message to Google Chat")

    async def stream_start(self, channel_id: str):
        pass

    async def stream_send(self, channel_id: str, chunk: str):
        pass

    async def stream_end(self, channel_id: str, error: str = None):
        pass

    async def update_idle_thread_name(self, channel_id: str, response: str):
        pass

    def _handle_incoming_attachments(self, chat_message: dict, message_id: str) -> str | None:
        """Extract and download attachments from incoming message.
        
        Returns JSON string of relative paths or None.
        """
        attachments_paths = []
        gchat_attachments = chat_message.get('attachment', [])
        if not gchat_attachments:
            return None
        
        cwd = self.gemini_config.get('workspace', '.')
        attachments_dir = self.gemini_config.get('attachments_dir', 'attachments')
        if not os.path.isabs(attachments_dir):
            attachments_dir = os.path.join(cwd, attachments_dir)
            
        try:
            os.makedirs(attachments_dir, exist_ok=True)
            
            credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/chat.messages.readonly'])
            
            service = build('chat', 'v1', credentials=credentials)
            
            for attachment in gchat_attachments:
                filename = attachment.get('contentName')
                logger.info(f"attachment: {filename}")
                
                # Get resourceName from attachmentDataRef
                data_ref = attachment.get('attachmentDataRef', {})
                resource_name = data_ref.get('resourceName')
                
                if resource_name:
                    ext = os.path.splitext(filename)[1]
                    if not ext:
                        content_type = attachment.get('contentType')
                        if content_type:
                            ext = mimetypes.guess_extension(content_type) or ''
                    safe_name = f"{uuid.uuid4()}{ext}"
                    filepath = os.path.join(attachments_dir, safe_name)
                    logger.info(f'save attachment saved to: {filepath}')
                    
                    request = service.media().download_media(resourceName=resource_name)
                    
                    with open(filepath, 'wb') as f:
                        downloader = MediaIoBaseDownload(f, request)
                        done = False
                        while done is False:
                            status, done = downloader.next_chunk()
                            
                    if filepath.startswith(os.path.abspath(cwd)):
                        rel_path = os.path.relpath(filepath, cwd)
                    else:
                        rel_path = filepath
                    attachments_paths.append(rel_path)
                else:
                    logger.warning(f"No resourceName found for attachment {filename}")
                    
            logger.info(f"Downloaded {len(attachments_paths)} attachments to {attachments_dir}")
        except Exception as e:
            logger.exception(f"Failed to download attachments")
            
        return json.dumps(attachments_paths) if attachments_paths else None

    def add_reaction(self, parent_message_name: str, emoji: str):
        """Add a reaction to a message."""
        logger.info(f"Adding reaction {emoji} to message {parent_message_name}")
        try:
            cred, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/chat.messages.reactions.create'])
            chat_service = build('chat', 'v1', credentials=cred)
            
            body = {
                "emoji": {
                    "unicode": emoji
                }
            }
            
            result = chat_service.spaces().messages().reactions().create(
                parent=parent_message_name,
                body=body
            ).execute()
            
            logger.info(f"Successfully added reaction: {result.get('name')}")
        except Exception as e:
            logger.warning(f"Failed to add reaction: {e}")

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
                # print(json.dumps(data, indent=2))
                
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
                        db.set_thread_active(channel_id)
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
                    
                    attachments_json = self._handle_incoming_attachments(chat_message, message_id)
                    
                    # Format prompt with content, author, and timestamp
                    prompt = f"{message_text}\n--- Message Above From {author_name} <@{author_id}> at {create_time} ---\n"
                    
                    logger.info(f"Inserting message from {author_name} in channel {channel_id}")
                    db.insert_message(channel_id, message_id, author_id, prompt, attachments=attachments_json)
                    
                    # Add reaction to demonstrate the feature
                    if message_id != 'unknown_message':
                        self.add_reaction(message_id, "👀")
                        
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
