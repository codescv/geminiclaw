import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import os
import sys
import tempfile

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from geminiclaw.agent import Agent

@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.user_id = "bot_123"
    bot.channel_exists = AsyncMock(return_value=True)
    bot.ensure_thread_for_cronjob = AsyncMock(return_value="thread_123")
    bot.send_message = AsyncMock()
    bot.typing = MagicMock()
    bot.typing.return_value.__aenter__ = AsyncMock()
    bot.typing.return_value.__aexit__ = AsyncMock()
    return bot

@pytest.mark.asyncio
async def test_run_cronjob_skip_if_empty_exists_not_empty(mock_bot):
    agent = Agent(bot=mock_bot, gemini_config={}, cronjobs=[])
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write("some content")
        temp_path = f.name
        
    prompt_file = tempfile.NamedTemporaryFile(mode='w', delete=False)
    prompt_file.write("run this")
    prompt_file.close()
    
    try:
        with patch('geminiclaw.agent.db') as mock_db:
            await agent.run_cronjob(
                prompt_file=prompt_file.name,
                channel_id="channel_123",
                skip_if_empty=temp_path
            )
            
            mock_db.insert_message.assert_called_once()
    finally:
        os.remove(temp_path)
        os.remove(prompt_file.name)

@pytest.mark.asyncio
async def test_run_cronjob_skip_if_empty_exists_empty(mock_bot):
    agent = Agent(bot=mock_bot, gemini_config={}, cronjobs=[])
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        temp_path = f.name
        
    prompt_file = tempfile.NamedTemporaryFile(mode='w', delete=False)
    prompt_file.write("run this")
    prompt_file.close()
    
    try:
        with patch('geminiclaw.agent.db') as mock_db:
            await agent.run_cronjob(
                prompt_file=prompt_file.name,
                channel_id="channel_123",
                skip_if_empty=temp_path
            )
            
            mock_db.insert_message.assert_not_called()
    finally:
        os.remove(temp_path)
        os.remove(prompt_file.name)

@pytest.mark.asyncio
async def test_run_cronjob_skip_if_empty_exists_whitespace_only(mock_bot):
    agent = Agent(bot=mock_bot, gemini_config={}, cronjobs=[])
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write("   \n   ")
        temp_path = f.name
        
    prompt_file = tempfile.NamedTemporaryFile(mode='w', delete=False)
    prompt_file.write("run this")
    prompt_file.close()
    
    try:
        with patch('geminiclaw.agent.db') as mock_db:
            await agent.run_cronjob(
                prompt_file=prompt_file.name,
                channel_id="channel_123",
                skip_if_empty=temp_path
            )
            
            mock_db.insert_message.assert_not_called()
    finally:
        os.remove(temp_path)
        os.remove(prompt_file.name)

@pytest.mark.asyncio
async def test_run_cronjob_skip_if_empty_not_exists(mock_bot):
    agent = Agent(bot=mock_bot, gemini_config={}, cronjobs=[])
    
    prompt_file = tempfile.NamedTemporaryFile(mode='w', delete=False)
    prompt_file.write("run this")
    prompt_file.close()
    
    try:
        with patch('geminiclaw.agent.db') as mock_db:
            await agent.run_cronjob(
                prompt_file=prompt_file.name,
                channel_id="channel_123",
                skip_if_empty="non_existent_file"
            )
            
            mock_db.insert_message.assert_not_called()
    finally:
        os.remove(prompt_file.name)
