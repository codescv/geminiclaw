import pytest
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from geminiclaw.chatbot import ChatBot
from geminiclaw.google_chat import GoogleChatBot

def test_google_chat_bot_inheritance():
    bot = GoogleChatBot(google_chat_config={})
    assert isinstance(bot, ChatBot)

@pytest.mark.asyncio
async def test_google_chat_bot_methods():
    bot = GoogleChatBot(google_chat_config={})
    assert bot.user_id == "google_chat_bot"
    assert bot.is_stream_off("channel_1") is False
    assert await bot.get_author_name("123") == "User_123"
    assert "Google Chat" in await bot.get_system_instructions("channel_1")
    assert await bot.channel_exists("channel_1") is True
    
    async with bot.typing("channel_1"):
        pass
        
    await bot.send_message("channel_1", "Hello")
    
    # Test other abstract methods that are stubs
    await bot.stream_start("channel_1")
    await bot.stream_send("channel_1", "chunk")
    await bot.stream_end("channel_1")
    await bot.update_idle_thread_name("channel_1", "response")
    await bot.ensure_thread_for_cronjob("channel_1", "prompt", "user", "session")

@pytest.mark.asyncio
async def test_google_chat_bot_pubsub():
    from unittest.mock import MagicMock, patch
    
    bot = GoogleChatBot(google_chat_config={
        'google_cloud_project': 'test-project',
        'google_chat_subscription': 'test-sub'
    })
    
    mock_subscriber = MagicMock()
    
    with patch('google.cloud.pubsub_v1.SubscriberClient', return_value=mock_subscriber):
        await bot.start()
        
    assert mock_subscriber.subscribe.called
    
    await bot.stop()

@pytest.mark.asyncio
async def test_google_chat_bot_add_reaction():
    from unittest.mock import MagicMock, patch
    
    bot = GoogleChatBot(google_chat_config={})
    
    mock_service = MagicMock()
    mock_messages = MagicMock()
    mock_reactions = MagicMock()
    mock_create = MagicMock()
    
    mock_service.spaces.return_value.messages.return_value.reactions.return_value = mock_reactions
    mock_reactions.create.return_value = mock_create
    mock_create.execute.return_value = {'name': 'spaces/1/messages/1/reactions/1'}
    
    mock_creds = MagicMock()
    mock_creds.universe_domain = 'googleapis.com'
    
    with patch('geminiclaw.google_chat.build', return_value=mock_service), \
         patch('google.auth.default', return_value=(mock_creds, 'project-id')):
        
        bot.add_reaction("spaces/1/messages/1", "👍")
        
    assert mock_reactions.create.called

@pytest.mark.asyncio
async def test_google_chat_bot_streaming():
    from unittest.mock import MagicMock, patch
    
    bot = GoogleChatBot(google_chat_config={
        'google_cloud_project': 'test-project',
        'google_chat_subscription': 'test-sub'
    })
    
    assert bot.is_stream_off("channel_1") is False
    
    mock_service = MagicMock()
    mock_messages = MagicMock()
    mock_create = MagicMock()
    mock_update = MagicMock()
    
    mock_service.spaces.return_value.messages.return_value = mock_messages
    mock_messages.create.return_value = mock_create
    mock_messages.update.return_value = mock_update
    
    mock_create.execute.return_value = {'name': 'spaces/1/messages/1'}
    mock_update.execute.return_value = {'name': 'spaces/1/messages/1'}
    
    mock_creds = MagicMock()
    
    with patch('geminiclaw.google_chat.build', return_value=mock_service), \
         patch('google.auth.default', return_value=(mock_creds, 'project-id')):
         
        await bot.stream_start("channel_1")
        assert "channel_1" in bot._current_streams
        assert bot._current_streams["channel_1"]['name'] == 'spaces/1/messages/1'
        
        await bot.stream_send("channel_1", "Hello")
        assert bot._current_streams["channel_1"]['content'] == 'Hello'
        
        await bot.stream_end("channel_1")
        assert "channel_1" not in bot._current_streams
        
    assert mock_messages.create.called
    assert mock_messages.update.called

@pytest.mark.asyncio
async def test_google_chat_bot_get_message_text():
    from unittest.mock import MagicMock, patch
    
    bot = GoogleChatBot(google_chat_config={
        'google_cloud_project': 'test-project'
    })
    
    mock_service = MagicMock()
    mock_messages = MagicMock()
    mock_get = MagicMock()
    
    mock_service.spaces.return_value.messages.return_value = mock_messages
    mock_messages.get.return_value = mock_get
    mock_get.execute.return_value = {'text': 'Hello World'}
    
    mock_creds = MagicMock()
    
    with patch('geminiclaw.google_chat.build', return_value=mock_service), \
         patch('google.auth.default', return_value=(mock_creds, 'project-id')):
         
        text = bot._get_message_content("spaces/1/messages/1")
        assert text == 'Hello World'
        
    assert mock_messages.get.called

@pytest.mark.asyncio
async def test_google_chat_bot_get_message_text_failure():
    from unittest.mock import MagicMock, patch
    
    bot = GoogleChatBot(google_chat_config={})
    
    with patch('google.auth.default', side_effect=Exception("Auth error")):
        text = bot._get_message_content("spaces/1/messages/1")
        assert text == ""

