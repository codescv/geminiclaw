import os
import tomllib
import sys

class Config:
    def __init__(self, path="config.toml"):
        try:
            with open(path, "rb") as f:
                self._raw_config = tomllib.load(f)
        except FileNotFoundError:
            print(f"Error: {path} not found. Please copy config.example.toml to config.toml and configure it.")
            sys.exit(1)

        self.discord = self._raw_config.get("discord", {})
        self.gemini = self._raw_config.get("gemini", {})
        
        self.token = self.discord.get("token")
        if not self.token:
            print("Error: discord.token not found in config.toml")
            sys.exit(1)
            
        self.proxy = os.getenv('HTTP_PROXY') or os.getenv('http_proxy') or os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
