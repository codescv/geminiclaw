import pytest
from unittest.mock import AsyncMock
import sys
import os
import discord

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from geminiclaw.bot import GeminiClawBot, StreamSender

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
    content = "Hello\nWorld"
    author_id = "123"
    prefix = f"<@{author_id}> " if author_id else ""
    sender = StreamSender(bot_instance, channel, prefix)
    await sender.send(content, flush=True)
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
    
    prefix = f"<@{author_id}> " if author_id else ""
    sender = StreamSender(bot_instance, channel, prefix)
    await sender.send(content, flush=True)
    
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

@pytest.mark.asyncio
async def test_process_pending_messages_timeout(bot_instance):
    from unittest.mock import patch, AsyncMock
    import asyncio
    
    with patch('geminiclaw.bot.db') as mock_db:
        mock_db.get_pending_message.return_value = {
            'id': 1,
            'channel_id': '123456',
            'prompt': 'Hello',
            'author_id': '789',
            'status': 'pending'
        }
        
        from unittest.mock import MagicMock
        channel = AsyncMock()
        channel.typing = MagicMock(return_value=AsyncMock())
        bot_instance.get_channel = MagicMock(return_value=channel)

        with patch('asyncio.create_subprocess_exec') as mock_exec:
            process = AsyncMock()
            process.stderr.read.return_value = b""
            mock_exec.return_value = process
            
            # Simulate a timeout inside the stream reader loop or during wait
            with patch('geminiclaw.bot.asyncio.wait_for', side_effect=asyncio.TimeoutError):
                await bot_instance.process_pending_messages()
                
            # Verify status update
            mock_db.update_message_status.assert_any_call(1, 'completed', 'Error: Gemini command timed out after 600 seconds.')

@pytest.mark.asyncio
async def test_process_pending_messages_json_error(bot_instance):
    from unittest.mock import patch, AsyncMock
    
    with patch('geminiclaw.bot.db') as mock_db:
        mock_db.get_pending_message.return_value = {
            'id': 1,
            'channel_id': '123456',
            'prompt': 'Hello',
            'author_id': '789',
            'status': 'pending'
        }
        
        from unittest.mock import MagicMock
        channel = AsyncMock()
        channel.typing = MagicMock(return_value=AsyncMock())
        bot_instance.get_channel = MagicMock(return_value=channel)

        with patch('asyncio.create_subprocess_exec') as mock_exec:
            process = AsyncMock()
            process.stderr.read.return_value = b""
            # Set up readline to return an invalid JSON line, then EOF
            process.stdout.readline.side_effect = [b'invalid json\n', b'']
            mock_exec.return_value = process
            
            await bot_instance.process_pending_messages()
            
            # The JSON error is caught and ignored, so it should run to completion
            mock_db.update_message_status.assert_any_call(1, 'delivered')

@pytest.mark.asyncio
async def test_process_pending_messages_outbound_attachments(bot_instance):
    from unittest.mock import patch, AsyncMock
    
    with patch('geminiclaw.bot.db') as mock_db:
        mock_db.get_pending_message.return_value = {
            'id': 1,
            'channel_id': '123456',
            'prompt': 'Hello',
            'author_id': '789',
            'status': 'pending'
        }
        
        from unittest.mock import MagicMock
        channel = AsyncMock()
        channel.typing = MagicMock(return_value=AsyncMock())
        bot_instance.get_channel = MagicMock(return_value=channel)

        with patch('asyncio.create_subprocess_exec') as mock_exec:
            process = AsyncMock()
            process.stderr.read.return_value = b""
            # Return valid JSON with attachment tag
            process.stdout.readline.side_effect = [
                b'{"type": "message", "role": "assistant", "content": "Here is the file [attachment: output.txt]"}',
                b''
            ]
            mock_exec.return_value = process
            
            # Mock os.path.isfile and discord.File to avoid real file access
            with patch('os.path.isfile', return_value=True), patch('discord.File'):
                await bot_instance.process_pending_messages()
                
            # It should have attempted to send the file to Discord
            assert channel.send.call_count > 0
            # Look for file parameter in any call
            file_sent = False
            for call in channel.send.call_args_list:
                kwargs = call[1]
                if 'files' in kwargs:
                    file_sent = True
                    break
            assert file_sent
@pytest.mark.asyncio
async def test_stream_sender_streaming_short():
    from unittest.mock import AsyncMock
    bot = AsyncMock()
    bot.max_response_length = 1900
    channel = AsyncMock()
    
    sender = StreamSender(bot, channel)
    await sender.send("Short stream text")
    
    channel.send.assert_called_once_with("Short stream text (incomplete)")
    assert sender.streamed == True
    assert sender.msg_to_edit is not None

@pytest.mark.asyncio
async def test_stream_sender_streaming_long_integration():
    from unittest.mock import AsyncMock
    bot = AsyncMock()
    bot.max_response_length = 10
    channel = AsyncMock()
    
    sender = StreamSender(bot, channel)
    await sender.send("Short") # 5 chars
    channel.send.assert_called_once_with("Short (incomplete)")
    
    # Set msg_to_edit to mock
    msg_to_edit = AsyncMock()
    sender.msg_to_edit = msg_to_edit
    
    await sender.send("OverflowText") # Total 5 + 12 = 17 chars > 10
    msg_to_edit.edit.assert_called_once_with(content="ShortOverf")
    channel.send.assert_called_with("lowText (incomplete)")
    assert sender.current_chunk == "lowText"

@pytest.mark.asyncio
async def test_stream_sender_non_streaming_short():
    from unittest.mock import AsyncMock
    bot = AsyncMock()
    bot.max_response_length = 1900
    channel = AsyncMock()
    
    sender = StreamSender(bot, channel)
    await sender.send("Short static text", flush=True)
    
    channel.send.assert_called_once_with("Short static text")
    assert sender.streamed == False
    assert sender.msg_to_edit is None

@pytest.mark.asyncio
async def test_stream_sender_non_streaming_long():
    from unittest.mock import AsyncMock
    bot = AsyncMock()
    bot.max_response_length = 10
    channel = AsyncMock()
    
    sender = StreamSender(bot, channel)
    await sender.send("Over flow text here", flush=True) 
    
    assert channel.send.call_count == 2
    channel.send.assert_any_call("Over flow ")
    channel.send.assert_any_call("text here")

@pytest.mark.asyncio
async def test_on_message_always_reply(bot_instance):
    from unittest.mock import AsyncMock, MagicMock
    
    # Configure always_reply
    bot_instance.always_reply = ["whitelisted_user", "12345"]
    
    # Mock message from whitelisted username
    message_username = AsyncMock()
    message_username.author.id = "67890" # Not in ID list
    message_username.author.name = "whitelisted_user"
    message_username.content = "Hello bot"
    message_username.channel = AsyncMock()
    message_username.mentions = []
    
    # Mock message from whitelisted ID
    message_id = AsyncMock()
    message_id.author.id = "12345"
    message_id.author.name = "normal_user"
    message_id.content = "Hello bot"
    message_id.channel = AsyncMock()
    message_id.mentions = []

    # Mock message from unknown user
    message_unknown = AsyncMock()
    message_unknown.author.id = "67890"
    message_unknown.author.name = "unknown_user"
    message_unknown.content = "Hello bot"
    message_unknown.channel = AsyncMock()
    message_unknown.mentions = []

    # Mock user.mentioned_in
    bot_instance.user.mentioned_in = MagicMock(return_value=False)
    
    from unittest.mock import patch
    with patch('geminiclaw.bot.db') as mock_db:
        # Test username whitelist
        await bot_instance.on_message(message_username)
        assert message_username.add_reaction.call_count == 1 # Reaction added because it should reply

        # Test ID whitelist
        await bot_instance.on_message(message_id)
        assert message_id.add_reaction.call_count == 1 # Reaction added

        # Test unknown user (should NOT reply)
        await bot_instance.on_message(message_unknown)
        assert message_unknown.add_reaction.call_count == 0 # No reaction added
