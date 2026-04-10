import pytest
import asyncio
from unittest.mock import AsyncMock
import sys
import os
import discord

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from geminiclaw.bot import DiscordBot, StreamSender

@pytest.fixture
def bot_instance():
    from unittest.mock import patch, MagicMock, PropertyMock, AsyncMock
    intents = discord.Intents.default()
    bot = DiscordBot(gemini_config={}, command_prefix="!", intents=intents)
    
    agent = MagicMock()
    agent.running_processes = {}
    agent.run_cronjob = AsyncMock()
    agent.process_single_message = AsyncMock()
    bot.agent = agent
    
    # Patch the user property
    patcher = patch('geminiclaw.bot.DiscordBot.user', new_callable=PropertyMock)
    mock_user = patcher.start()
    mock_user.return_value = MagicMock(id="12345")
    
    yield bot
    
    patcher.stop()
 
@pytest.mark.asyncio
async def test_send_long_message_short(bot_instance):
    channel = AsyncMock()
    content = "Hello world"
    sender = StreamSender(bot_instance, channel)
    await sender.send(content, flush=True)
    channel.send.assert_called_once_with("Hello world")

@pytest.mark.asyncio
async def test_send_long_message_lines_split(bot_instance):
    channel = AsyncMock()
    # Create two lines that together exceed max_response_length but individually fit
    line1 = "a" * 1500 + "\n"
    line2 = "b" * 500
    content = line1 + line2
    
    sender = StreamSender(bot_instance, channel)
    await sender.send(content, flush=True)
    
    assert channel.send.call_count == 2
    calls = channel.send.call_args_list
    assert calls[0][0][0] == line1
    assert calls[1][0][0] == line2

@pytest.mark.asyncio
async def test_send_long_message_hard_split(bot_instance):
    channel = AsyncMock()
    # Create a single line that exceeds max_response_length
    content = "a" * (bot_instance.max_response_length + 10)
    sender = StreamSender(bot_instance, channel)
    await sender.send(content, flush=True)
    
    assert channel.send.call_count == 2
    calls = channel.send.call_args_list
    assert calls[0][0][0] == "a" * bot_instance.max_response_length
    assert calls[1][0][0] == "a" * 10

@pytest.mark.asyncio
async def test_send_long_message_mixed_split(bot_instance):
    channel = AsyncMock()
    # line1 fits
    line1 = "a" * 100 + "\n"
    # line2 is huge
    line2 = "b" * (bot_instance.max_response_length + 100) + "\n"
    # line3 fits
    line3 = "c" * 100
    
    content = line1 + line2 + line3
    sender = StreamSender(bot_instance, channel)
    await sender.send(content, flush=True)
    
    assert channel.send.call_count == 3
    calls = channel.send.call_args_list
    assert calls[0][0][0] == line1
    assert calls[1][0][0] == ("b" * (bot_instance.max_response_length + 100) + "\n")[:bot_instance.max_response_length]
    assert calls[2][0][0] == ("b" * 100) + "\n" + line3

@pytest.mark.asyncio
async def test_send_long_message_with_mention(bot_instance):
    channel = AsyncMock()
    content = "<@123> Hello\nWorld"
    sender = StreamSender(bot_instance, channel)
    await sender.send(content, flush=True)
    # Should be sent in one go if it fits
    channel.send.assert_called_once_with(content)

@pytest.mark.asyncio
async def test_send_long_message_split_with_mention(bot_instance):
    channel = AsyncMock()
    # line1 fits but adding line2 overflows
    line1 = "<@123> " + "a" * 1500 + "\n"
    line2 = "b" * 500
    content = line1 + line2
    
    sender = StreamSender(bot_instance, channel)
    await sender.send(content, flush=True)
    
    assert channel.send.call_count == 2
    calls = channel.send.call_args_list
    # First chunk has mention
    assert calls[0][0][0] == line1
    # Second chunk does NOT have mention
    assert calls[1][0][0] == line2
