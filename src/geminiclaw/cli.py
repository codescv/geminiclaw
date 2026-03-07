import sys
import shutil
from enum import Enum

import typer

from .db import init_db
from .service import install as service_install, start as service_start, stop as service_stop, status as service_status

app = typer.Typer(help="Gemini Claw CLI")

@app.command(help="Initialize config and database")
def init():
    # Initialize DB
    init_db()
    # Check config.toml
    if not shutil.os.path.exists("config.toml") and shutil.os.path.exists("config.example.toml"):
        shutil.copy("config.example.toml", "config.toml")
        print("Created config.toml from config.example.toml. Please configure it.")
    elif not shutil.os.path.exists("config.toml"):
        print("Warning: config.toml not found and config.example.toml is missing.")
    elif shutil.os.path.exists("config.toml"):
        print("config.toml already exists.")
    print("Initialization complete. Please ensure you have set all variables in config.toml.")

@app.command(help="Start the bot directly")
def start():
    from .bot import main as bot_main
    print("Starting Gemini Claw bot...")
    bot_main()

class ServiceAction(str, Enum):
    install = "install"
    start = "start"
    stop = "stop"
    status = "status"

@app.command(help="Manage the macOS background service")
def service(action: ServiceAction = typer.Argument(..., help="Action to perform")):
    if action == ServiceAction.install:
        service_install()
    elif action == ServiceAction.start:
        service_start()
    elif action == ServiceAction.stop:
        service_stop()
    elif action == ServiceAction.status:
        service_status()

if __name__ == "__main__":
    app()
