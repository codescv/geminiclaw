import sys
import shutil
import os
from enum import Enum

import typer

from .db import init_db
from .service import install as service_install, start as service_start, stop as service_stop, status as service_status, restart as service_restart

app = typer.Typer(help="Gemini Claw CLI")

@app.command(help="Initialize config and database")
def init():
    # Initialize DB
    init_db()
    # Check config.toml
    if not os.path.exists("config.toml"):
        try:
            import importlib.resources
            example_content = importlib.resources.files("geminiclaw.resources").joinpath("config.example.toml").read_text()
            with open("config.toml", "w") as f:
                f.write(example_content)
            print("Created config.toml from bundled example. Please configure it.")
        except Exception as e:
            print(f"Warning: config.toml not found and bundled config.example.toml is missing: {e}")
        print("Initialization complete. Please ensure you have set all variables in config.toml.")
    else:
        print("config.toml already exists.")


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
    restart = "restart"

@app.command(help="Manage the background service")
def service(
    action: ServiceAction = typer.Argument(..., help="Action to perform"),
    service_name: str = typer.Option("com.codescv.geminiclaw", "--service-name", help="Name of the service")
):
    if action == ServiceAction.install:
        service_install(service_name)
    elif action == ServiceAction.start:
        service_start(service_name)
    elif action == ServiceAction.stop:
        service_stop(service_name)
    elif action == ServiceAction.status:
        service_status(service_name)
    elif action == ServiceAction.restart:
        service_restart(service_name)

if __name__ == "__main__":
    app()
