import pytest
from unittest.mock import AsyncMock
import sys
import os
import discord

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from geminiclaw.bot import GeminiClawBot

@pytest.fixture
def bot_instance():
    from unittest.mock import patch, MagicMock, PropertyMock
    intents = discord.Intents.default()
    bot = GeminiClawBot(gemini_config={}, command_prefix="!", intents=intents)
    
    # Patch the user property
    patcher = patch('geminiclaw.bot.GeminiClawBot.user', new_callable=PropertyMock)
    mock_user = patcher.start()
    mock_user.return_value = MagicMock(id="12345")
    
    yield bot
    
    patcher.stop()
 
@pytest.mark.asyncio
async def test_send_long_message_short(bot_instance):
    channel = AsyncMock()
    content = "Hello world"
    await bot_instance.send_long_message(channel, content)
    channel.send.assert_called_once_with("Hello world")

@pytest.mark.asyncio
async def test_send_long_message_lines_split(bot_instance):
    channel = AsyncMock()
    # Create two lines that together exceed max_response_length but individually fit
    line1 = "a" * 1500 + "\n"
    line2 = "b" * 500
    content = line1 + line2
    
    await bot_instance.send_long_message(channel, content)
    
    assert channel.send.call_count == 2
    calls = channel.send.call_args_list
    assert calls[0][0][0] == line1
    assert calls[1][0][0] == line2

@pytest.mark.asyncio
async def test_send_long_message_hard_split(bot_instance):
    channel = AsyncMock()
    # Create a single line that exceeds max_response_length
    content = "a" * (bot_instance.max_response_length + 10)
    await bot_instance.send_long_message(channel, content)
    
    assert channel.send.call_count == 1
    calls = channel.send.call_args_list
    assert calls[0][0][0] == "a" * bot_instance.max_response_length

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
    await bot_instance.send_long_message(channel, content)
    
    assert channel.send.call_count == 3
    calls = channel.send.call_args_list
    assert calls[0][0][0] == line1
    # Second call is line2 truncated
    assert calls[1][0][0] == ("b" * (bot_instance.max_response_length + 100) + "\n")[:bot_instance.max_response_length]
    assert calls[2][0][0] == line3

@pytest.mark.asyncio
async def test_send_long_message_with_mention(bot_instance):
    channel = AsyncMock()
    content = "Hello\nWorld"
    author_id = "123"
    await bot_instance.send_long_message(channel, content, author_id=author_id)
    # Should be sent in one go if it fits
    channel.send.assert_called_once_with(f"<@123> {content}")

@pytest.mark.asyncio
async def test_send_long_message_split_with_mention(bot_instance):
    channel = AsyncMock()
    # line1 fits but adding line2 overflows
    line1 = "a" * 1500 + "\n"
    line2 = "b" * 500
    content = line1 + line2
    author_id = "123"
    
    await bot_instance.send_long_message(channel, content, author_id=author_id)
    
    assert channel.send.call_count == 2
    calls = channel.send.call_args_list
    # First chunk has mention
    assert calls[0][0][0] == f"<@123> {line1}"
    # Second chunk does NOT have mention
    assert calls[1][0][0] == line2

@pytest.mark.asyncio
async def test_process_pending_messages_with_topic(bot_instance):
    from unittest.mock import patch, AsyncMock
    import os
    import discord
    
    # Mock db methods in the bot's imported db module
    with patch('geminiclaw.bot.db') as mock_db:
        mock_db.get_pending_message.return_value = {
            'id': 1,
            'channel_id': '123456',
            'prompt': 'Hello',
            'author_id': '789',
            'status': 'pending'
        }
        mock_db.get_thread_session.return_value = None
        
        # Mock channel using spec to pass isinstance check
        channel = AsyncMock(spec=discord.TextChannel)
        channel.topic = "You are a helpful assistant."
        
        # Setup history mock as an async generator
        async def mock_history(*args, **kwargs):
            for msg in []:
                yield msg
        channel.history.side_effect = mock_history
        
        from unittest.mock import MagicMock
        bot_instance.get_channel = MagicMock(return_value=channel)

        
        # Mock asyncio.create_subprocess_exec
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            process = AsyncMock()
            process.communicate.return_value = (b'{"response": "Hi"}', b'')
            mock_exec.return_value = process
            
            # Run
            await bot_instance.process_pending_messages()
            
            # Verify env has GEMINI_SYSTEM_MD
            args, kwargs = mock_exec.call_args
            env = kwargs.get('env')
            assert env is not None
            assert 'GEMINI_SYSTEM_MD' in env
            assert env['GEMINI_SYSTEM_MD'].startswith('/tmp/gemini_system_')
            
            # Verify file was cleaned up by finally block
            file_path = env['GEMINI_SYSTEM_MD']
            assert os.path.exists(file_path) == False

@pytest.mark.asyncio
async def test_process_pending_messages_with_yolo_config(bot_instance):
    from unittest.mock import patch, AsyncMock
    
    bot_instance.gemini_config['yolo'] = True

    with patch('geminiclaw.bot.db') as mock_db:
        mock_db.get_pending_message.return_value = {
            'id': 1,
            'channel_id': '123456',
            'prompt': 'Hello',
            'author_id': '789',
            'status': 'pending'
        }
        mock_db.get_thread_session.return_value = None
        
        bot_instance.get_channel = AsyncMock(return_value=None)
        bot_instance.fetch_channel = AsyncMock(return_value=None)

        with patch('asyncio.create_subprocess_exec') as mock_exec:
            process = AsyncMock()
            process.communicate.return_value = (b'{"response": "Hi"}', b'')
            mock_exec.return_value = process
            
            await bot_instance.process_pending_messages()
            
            args, _ = mock_exec.call_args
            assert '-y' in args

@pytest.mark.asyncio
async def test_process_pending_messages_with_yolo_prompt(bot_instance):
    from unittest.mock import patch, AsyncMock
    
    with patch('geminiclaw.bot.db') as mock_db:
        mock_db.get_pending_message.return_value = {
            'id': 1,
            'channel_id': '123456',
            'prompt': '-y Hello',
            'author_id': '789',
            'status': 'pending'
        }
        mock_db.get_thread_session.return_value = None
        
        bot_instance.get_channel = AsyncMock(return_value=None)
        bot_instance.fetch_channel = AsyncMock(return_value=None)
        from unittest.mock import MagicMock
        bot_instance.get_user = MagicMock()
        mock_author = MagicMock()
        mock_author.display_name = 'TestUser'
        bot_instance.get_user.return_value = mock_author

        with patch('asyncio.create_subprocess_exec') as mock_exec:
            process = AsyncMock()
            process.communicate.return_value = (b'{"response": "Hi"}', b'')
            mock_exec.return_value = process
            
            await bot_instance.process_pending_messages()
            
            args, _ = mock_exec.call_args
            assert '-y' in args
            # Also verify that the prompt passed to Gemini is just "Hello", not "-y Hello"
            # It should be passed after -p
            p_index = args.index('-p')
            assert args[p_index + 1] == 'TestUser: Hello'

@pytest.mark.asyncio
async def test_process_pending_messages_with_attachments(bot_instance):
    from unittest.mock import patch, AsyncMock
    
    with patch('geminiclaw.bot.db') as mock_db:
        mock_db.get_pending_message.return_value = {
            'id': 1,
            'channel_id': '123456',
            'prompt': 'Analyze this',
            'author_id': '789',
            'status': 'pending',
            'attachments': '["attachments/file1.txt"]'
        }
        mock_db.get_thread_session.return_value = None
        
        bot_instance.get_channel = AsyncMock(return_value=None)
        bot_instance.fetch_channel = AsyncMock(return_value=None)
        
        from unittest.mock import MagicMock
        bot_instance.get_user = MagicMock()
        mock_author = MagicMock()
        mock_author.display_name = 'TestUser'
        bot_instance.get_user.return_value = mock_author

        with patch('asyncio.create_subprocess_exec') as mock_exec:
            process = AsyncMock()
            process.communicate.return_value = (b'{"response": "Hi"}', b'')
            mock_exec.return_value = process
            
            await bot_instance.process_pending_messages()
            
            args, _ = mock_exec.call_args
            p_index = args.index('-p')
            prompt_arg = args[p_index + 1]
            
            assert 'TestUser: Analyze this' in prompt_arg
            assert 'Attachments:' in prompt_arg
            assert '- attachments/file1.txt' in prompt_arg
