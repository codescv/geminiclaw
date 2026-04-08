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

    # Initialize workspace files
    try:
        import importlib.resources
        import filecmp
        from contextlib import ExitStack

        resource_path = importlib.resources.files("geminiclaw.resources").joinpath("workspace")
        with ExitStack() as stack:
            workspace_dir = stack.enter_context(importlib.resources.as_file(resource_path))
            for root, dirs, files in os.walk(workspace_dir):
                rel_path = os.path.relpath(root, workspace_dir)
                target_dir = os.path.join(".", rel_path) if rel_path != "." else "."
                os.makedirs(target_dir, exist_ok=True)
                for file in files:
                    src_file = os.path.join(root, file)
                    dst_file = os.path.join(target_dir, file)
                    if os.path.exists(dst_file):
                        if not filecmp.cmp(src_file, dst_file, shallow=False):
                            print(f"Warning: {dst_file} differs from the bundled workspace version and was skipped.")
                    else:
                        shutil.copy2(src_file, dst_file)
                        print(f"Copied {dst_file}")
        print("Initialization complete. Please do the following steps:")
        print("- Ensure you have set all variables in `config.toml.`")
        print("- Run `./bootstrap.sh` to initialize the Gemini workspace.")
        print("- Edit `instructions/User.md` to let the agent know more about you.")
        print("- Run geminiclaw service install to install this as a background service.")
    except Exception as e:
        print(f"Warning: failed to copy workspace resources: {e}")


@app.command(help="Start the bot directly")
def start(
    service_name: str = typer.Option("com.codescv.geminiclaw", "--service-name", help="Name of the service")
):
    from .bot import main as bot_main
    print(f"Starting Gemini Claw bot using service name {service_name}...")
    bot_main(service_name=service_name)

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
