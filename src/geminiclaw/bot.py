import os
import signal
import json
import asyncio
import subprocess
import time
import re
import random
import discord
from . import db
from .config import Config
from .discord import DiscordBot, StreamSender
from .agent import Agent

def main(service_name="com.codescv.geminiclaw"):
    config = Config()

    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    bot = DiscordBot(
        gemini_config=config.gemini,
        service_name=service_name,
        always_reply=config.always_reply,
        stream_off_channels=config.stream_off_channels,
        command_prefix="!",
        intents=intents,
        proxy=config.proxy
    )

    agent = Agent(
        bot=bot,
        gemini_config=config.gemini,
        prompt_config=config.prompt,
        policy=config.policy,
        cronjobs=config.cronjobs
    )

    bot.agent = agent

    bot.run(config.token)

if __name__ == "__main__":
    main()
