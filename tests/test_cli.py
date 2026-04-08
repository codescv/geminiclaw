import os
import shutil
import pytest
from typer.testing import CliRunner
from geminiclaw.cli import app

runner = CliRunner()

def test_init_command(tmp_path, monkeypatch):
    # Change working directory to tmp_path for the test
    monkeypatch.chdir(tmp_path)
    
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    
    # Verify config.toml was copied
    assert os.path.exists("config.toml")
    
    # Verify some workspace directories were created
    assert os.path.isdir("cronjobs")
    assert os.path.isdir("instructions")
    assert os.path.isdir("examples")
