import pytest
from unittest.mock import AsyncMock
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from bot import send_long_message, MAX_RESPONSE_LENGTH

@pytest.mark.asyncio
async def test_send_long_message_short():
    channel = AsyncMock()
    content = "Hello world"
    await send_long_message(channel, content)
    channel.send.assert_called_once_with("Hello world")

@pytest.mark.asyncio
async def test_send_long_message_lines_split():
    channel = AsyncMock()
    # Create two lines that together exceed MAX_RESPONSE_LENGTH but individually fit
    line1 = "a" * 1500 + "\n"
    line2 = "b" * 500
    content = line1 + line2
    
    await send_long_message(channel, content)
    
    assert channel.send.call_count == 2
    calls = channel.send.call_args_list
    assert calls[0][0][0] == line1
    assert calls[1][0][0] == line2

@pytest.mark.asyncio
async def test_send_long_message_hard_split():
    channel = AsyncMock()
    # Create a single line that exceeds MAX_RESPONSE_LENGTH
    # New logic truncates instead of splitting
    content = "a" * (MAX_RESPONSE_LENGTH + 10)
    await send_long_message(channel, content)
    
    assert channel.send.call_count == 1
    calls = channel.send.call_args_list
    assert calls[0][0][0] == "a" * MAX_RESPONSE_LENGTH

@pytest.mark.asyncio
async def test_send_long_message_mixed_split():
    channel = AsyncMock()
    # line1 fits
    line1 = "a" * 100 + "\n"
    # line2 is huge
    line2 = "b" * (MAX_RESPONSE_LENGTH + 100) + "\n"
    # line3 fits
    line3 = "c" * 100
    
    content = line1 + line2 + line3
    await send_long_message(channel, content)
    
    # Expected behavior:
    # 1. line1 sent
    # 2. line2 (truncated) sent
    # 3. line3 sent
    
    assert channel.send.call_count == 3
    calls = channel.send.call_args_list
    assert calls[0][0][0] == line1
    # Second call is line2 truncated
    assert calls[1][0][0] == ("b" * (MAX_RESPONSE_LENGTH + 100) + "\n")[:MAX_RESPONSE_LENGTH]
    assert calls[2][0][0] == line3

@pytest.mark.asyncio
async def test_send_long_message_with_mention():
    channel = AsyncMock()
    content = "Hello\nWorld"
    author_id = "123"
    await send_long_message(channel, content, author_id=author_id)
    # Should be sent in one go if it fits
    channel.send.assert_called_once_with(f"<@123> {content}")

@pytest.mark.asyncio
async def test_send_long_message_split_with_mention():
    channel = AsyncMock()
    # line1 fits but adding line2 overflows
    line1 = "a" * 1500 + "\n"
    line2 = "b" * 500
    content = line1 + line2
    author_id = "123"
    
    await send_long_message(channel, content, author_id=author_id)
    
    assert channel.send.call_count == 2
    calls = channel.send.call_args_list
    # First chunk has mention
    assert calls[0][0][0] == f"<@123> {line1}"
    # Second chunk does NOT have mention
    assert calls[1][0][0] == line2
