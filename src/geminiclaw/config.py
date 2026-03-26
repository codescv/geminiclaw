import os
import tomllib
import sys

class Config:
    def __init__(self, path="config.toml"):
        paths = [path]
        self._raw_config = {}
        loaded = False
        for p in paths:
            if os.path.exists(p):
                try:
                    with open(p, "rb") as f:
                        self._raw_config = tomllib.load(f)
                    loaded = True
                    break
                except Exception as e:
                    print(f"Error loading {p}: {e}")
        
        if not loaded:
            print(f"Error: Config file not found in {paths}. Please copy config.example.toml to config.toml and configure it.")
            sys.exit(1)

        self.discord = self._raw_config.get("discord", {})
        self.gemini = self._raw_config.get("gemini", {})
        self.cronjobs = self._raw_config.get("cronjob", [])
        self.prompt = self._raw_config.get("prompt", {})
 
        self.always_reply = self.discord.get("always_reply", [])
        
        self.token = self.discord.get("token")
        if not self.token:
            print("Error: discord.token not found in config.toml")
            sys.exit(1)
            
        self.proxy = os.getenv('HTTP_PROXY') or os.getenv('http_proxy') or os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
