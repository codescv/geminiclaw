import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from geminiclaw.bot import DiscordBot

@pytest.fixture
def bot_instance():
    from unittest.mock import PropertyMock
    intents = discord.Intents.default()
    bot = DiscordBot(gemini_config={}, command_prefix="!", intents=intents)
    bot.agent = MagicMock()
    bot.agent.running_processes = {}
    bot.service_name = "test_service"
    
    # Patch user
    patcher = patch('geminiclaw.bot.DiscordBot.user', new_callable=PropertyMock)
    mock_user = patcher.start()
    mock_user.return_value = MagicMock(id=12345, name="Bot")
    
    # Mock tree.sync
    bot.tree.sync = AsyncMock()
    
    yield bot
    patcher.stop()

@pytest.mark.asyncio
async def test_slash_stop(bot_instance):
    interaction = AsyncMock()
    interaction.channel = MagicMock(spec=discord.Thread)
    interaction.channel.id = 123
    
    await bot_instance.setup_hook()
    
    stop_cmd = bot_instance.tree.get_command("stop")
    assert stop_cmd is not None
    
    with patch('geminiclaw.db.set_thread_active') as mock_set_active:
        await stop_cmd.callback(interaction)
        mock_set_active.assert_called_once_with(123, False)
        interaction.response.send_message.assert_called_once_with("🛑 Thread deactivated.")

@pytest.mark.asyncio
async def test_slash_stop_not_thread(bot_instance):
    interaction = AsyncMock()
    interaction.channel = MagicMock(spec=discord.TextChannel)
    interaction.channel.id = 123
    
    await bot_instance.setup_hook()
    
    stop_cmd = bot_instance.tree.get_command("stop")
    await stop_cmd.callback(interaction)
    
    interaction.response.send_message.assert_called_once_with("This command can only be used in threads.", ephemeral=True)

@pytest.mark.asyncio
async def test_slash_continue(bot_instance):
    interaction = AsyncMock()
    interaction.channel = MagicMock(spec=discord.Thread)
    interaction.channel.id = 123
    
    await bot_instance.setup_hook()
    
    cnt_cmd = bot_instance.tree.get_command("continue")
    assert cnt_cmd is not None
    
    with patch('geminiclaw.db.set_thread_active') as mock_set_active:
        await cnt_cmd.callback(interaction)
        mock_set_active.assert_called_once_with(123, True)
        interaction.response.send_message.assert_called_once_with("▶️ Thread reactivated.")

@pytest.mark.asyncio
async def test_slash_kill_found(bot_instance):
    interaction = AsyncMock()
    interaction.channel = MagicMock()
    interaction.channel.id = 123
    
    process = MagicMock()
    process.pid = 999
    bot_instance.agent.running_processes["123"] = process
    
    await bot_instance.setup_hook()
    
    kill_cmd = bot_instance.tree.get_command("kill")
    assert kill_cmd is not None
    
    with patch('os.killpg') as mock_killpg:
        await kill_cmd.callback(interaction)
        mock_killpg.assert_called_once()
        interaction.response.send_message.assert_called_once_with("💀 Process killed.")

@pytest.mark.asyncio
async def test_slash_kill_not_found(bot_instance):
    interaction = AsyncMock()
    interaction.channel = MagicMock()
    interaction.channel.id = 123
    
    await bot_instance.setup_hook()
    
    kill_cmd = bot_instance.tree.get_command("kill")
    await kill_cmd.callback(interaction)
    
    interaction.response.send_message.assert_called_once_with("No running process found for this channel.", ephemeral=True)

@pytest.mark.asyncio
async def test_slash_restart(bot_instance):
    interaction = AsyncMock()
    
    await bot_instance.setup_hook()
    
    restart_cmd = bot_instance.tree.get_command("restart")
    assert restart_cmd is not None
    
    with patch('subprocess.Popen') as mock_popen:
        await restart_cmd.callback(interaction)
        mock_popen.assert_called_once()
        interaction.response.send_message.assert_called_once_with("🔄 Restarting service...")
