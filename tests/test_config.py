import pytest
import os
import sys
import tempfile

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from geminiclaw.config import Config

def test_config_load_success():
    # Create a temporary config file
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write('''
[discord]
token = "test_token"

[gemini]
workspace = "/tmp"
''')
        temp_path = f.name

    try:
        config = Config(path=temp_path)
        assert config.token == "test_token"
        assert config.discord.get("token") == "test_token"
        assert config.gemini.get("workspace") == "/tmp"
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def test_config_file_not_found():
    with pytest.raises(SystemExit) as excinfo:
        Config(path="non_existent_config.toml")
    assert excinfo.value.code == 1

def test_config_missing_token():
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write('''
[discord]
# token is missing
''')
        temp_path = f.name

    try:
        with pytest.raises(SystemExit) as excinfo:
            Config(path=temp_path)
        assert excinfo.value.code == 1
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def test_config_proxy_env(monkeypatch):
    # Test proxy detection
    monkeypatch.setenv('HTTP_PROXY', 'http://proxy.example.com')
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write('''
[discord]
token = "test_token"
''')
        temp_path = f.name

    try:
        config = Config(path=temp_path)
        assert config.proxy == 'http://proxy.example.com'
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
