from abc import ABC, abstractmethod
from contextlib import asynccontextmanager

class ChatBot(ABC):
    """
    Abstract base class for Chat Bots in Gemini Claw.
    Defines the public interface that the Agent expects.
    """

    @property
    @abstractmethod
    def user_id(self) -> str:
        """Get the bot's user ID."""
        pass

    @abstractmethod
    def is_stream_off(self, channel_id: str) -> bool:
        """Check if streaming is turned off for a channel."""
        pass

    @abstractmethod
    async def get_author_name(self, author_id: str) -> str:
        """Get the author's name by ID."""
        pass

    @abstractmethod
    async def get_system_instructions(self, channel_id: str) -> str:
        """Get system instructions for the bot in a specific channel."""
        pass

    @abstractmethod
    @asynccontextmanager
    def typing(self, channel_id: str):
        """Show typing indicator."""
        pass

    @abstractmethod
    async def channel_exists(self, channel_id: str) -> bool:
        """Check if a channel exists."""
        pass

    @abstractmethod
    async def ensure_thread_for_cronjob(self, channel_id: str, prompt: str, mention_user_id: str, gemini_session_id: str) -> str:
        """Ensure a thread exists for a cronjob."""
        pass

    @abstractmethod
    async def send_message(self, channel_id: str, content: str):
        """Send a message to a channel."""
        pass

    @abstractmethod
    async def stream_start(self, channel_id: str):
        """Start a stream."""
        pass

    @abstractmethod
    async def stream_send(self, channel_id: str, chunk: str):
        """Send a chunk to a stream."""
        pass

    @abstractmethod
    async def stream_end(self, channel_id: str, error: str = None):
        """End a stream."""
        pass

    @abstractmethod
    async def update_idle_thread_name(self, channel_id: str, response: str):
        """Update the thread name if idle."""
        pass

    @abstractmethod
    def run(self, token: str = None):
        """Run the bot."""
        pass
