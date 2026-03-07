import os
import sys
import subprocess
from pathlib import Path
import shutil

PLIST_LABEL = "com.gemini.claw"
PLIST_FILENAME = f"{PLIST_LABEL}.plist"
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
PLIST_PATH = LAUNCH_AGENTS_DIR / PLIST_FILENAME

SYSTEMD_SERVICE_NAME = "geminiclaw.service"
SYSTEMD_USER_DIR = Path.home() / ".config" / "systemd" / "user"
SYSTEMD_SERVICE_PATH = SYSTEMD_USER_DIR / SYSTEMD_SERVICE_NAME

ENV_VARS = [
    'HTTP_PROXY', 'HTTPS_PROXY', 
    'GOOGLE_API_KEY', 'GOOGLE_CLOUD_PROJECT', 'GOOGLE_CLOUD_LOCATION',
]

def get_executable_path(executable_name):
    path = shutil.which(executable_name)
    if not path:
        # Fallback to common locations if not in PATH during execution
        common_paths = [Path.home() / ".cargo" / "bin" / executable_name, Path.home() / ".local" / "bin" / executable_name]
        for p in common_paths:
            if p.exists():
                return str(p)
    return path

def install_macos(project_dir, geminiclaw_path, env_vars):
    env_vars_str = "\n".join([f"        <key>{k}</key>\n        <string>{v}</string>" for k, v in env_vars.items() if v])
        
    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{geminiclaw_path}</string>
        <string>start</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{project_dir}</string>
    <key>StandardOutPath</key>
    <string>{project_dir / "claw.log"}</string>
    <key>StandardErrorPath</key>
    <string>{project_dir / "claw.error.log"}</string>
    <key>EnvironmentVariables</key>
    <dict>
{env_vars_str}
    </dict>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_text(plist_content)
    print(f"Installed launchd service at {PLIST_PATH}")

def install_linux(project_dir, geminiclaw_path, env_vars):
    env_lines = "\n".join([f'Environment="{k}={v}"' for k, v in env_vars.items() if v])
    service_content = f"""[Unit]
Description=Gemini Claw Service
After=network.target

[Service]
Type=simple
ExecStart={geminiclaw_path} start
WorkingDirectory={project_dir}
StandardOutput=append:{project_dir}/claw.log
StandardError=append:{project_dir}/claw.error.log
{env_lines}

[Install]
WantedBy=default.target
"""
    SYSTEMD_USER_DIR.mkdir(parents=True, exist_ok=True)
    SYSTEMD_SERVICE_PATH.write_text(service_content)
    subprocess.run(["systemctl", "--user", "daemon-reload"])
    subprocess.run(["systemctl", "--user", "enable", SYSTEMD_SERVICE_NAME])
    print(f"Installed systemd service at {SYSTEMD_SERVICE_PATH}")

def install():
    project_dir = Path.cwd()
    geminiclaw_path = get_executable_path("geminiclaw")
    if not geminiclaw_path:
        print("Error: 'geminiclaw' executable not found. Please ensure it is installed or in PATH.")
        sys.exit(1)
        
    # Get the current PATH and proxies to ensure the bot can work correctly when launched by launchd/systemd
    env_vars = {
        "PATH": os.environ.get('PATH', '/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin'),
        "PYTHONUNBUFFERED": "1",
    }

    for key in ENV_VARS:
        if key in os.environ:
            env_vars[key] = os.environ[key]

    if sys.platform == "darwin":
        install_macos(project_dir, geminiclaw_path, env_vars)
    elif sys.platform == "linux":
        install_linux(project_dir, geminiclaw_path, env_vars)
    else:
        print(f"Unsupported platform: {sys.platform}")
        sys.exit(1)

def start():
    if sys.platform == "darwin":
        if not PLIST_PATH.exists():
            print(f"Error: Service not installed at {PLIST_PATH}.")
            print("Please run 'geminiclaw service install' first.")
            sys.exit(1)
            
        print(f"Loading and starting {PLIST_LABEL}...")
        subprocess.run(["launchctl", "load", "-w", str(PLIST_PATH)])
        subprocess.run(["launchctl", "start", PLIST_LABEL])
        print("Service started! Logs are available in claw.log and claw.error.log.")
    elif sys.platform == "linux":
        if not SYSTEMD_SERVICE_PATH.exists():
            print(f"Error: Service not installed at {SYSTEMD_SERVICE_PATH}.")
            print("Please run 'geminiclaw service install' first.")
            sys.exit(1)
            
        print(f"Starting {SYSTEMD_SERVICE_NAME}...")
        subprocess.run(["systemctl", "--user", "start", SYSTEMD_SERVICE_NAME])
        print("Service started! Logs are available in claw.log and claw.error.log.")
    else:
        print(f"Unsupported platform: {sys.platform}")
        sys.exit(1)

def stop():
    if sys.platform == "darwin":
        if not PLIST_PATH.exists():
            print("Service not installed. Nothing to stop.")
            return
            
        print(f"Stopping and unloading {PLIST_LABEL}...")
        subprocess.run(["launchctl", "stop", PLIST_LABEL])
        subprocess.run(["launchctl", "unload", "-w", str(PLIST_PATH)])
        print("Service stopped.")
    elif sys.platform == "linux":
        if not SYSTEMD_SERVICE_PATH.exists():
            print("Service not installed. Nothing to stop.")
            return
            
        print(f"Stopping and disabling {SYSTEMD_SERVICE_NAME}...")
        subprocess.run(["systemctl", "--user", "stop", SYSTEMD_SERVICE_NAME])
        subprocess.run(["systemctl", "--user", "disable", SYSTEMD_SERVICE_NAME])
        print("Service stopped.")
    else:
        print(f"Unsupported platform: {sys.platform}")

def status():
    if sys.platform == "darwin":
        result = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
        found = False
        for line in result.stdout.splitlines():
            if PLIST_LABEL in line:
                print(f"Service status: {line.strip()}")
                found = True
                break
                
        if not found:
            print("Service is not currently loaded or running.")
    elif sys.platform == "linux":
        result = subprocess.run(["systemctl", "--user", "status", SYSTEMD_SERVICE_NAME], capture_output=True, text=True)
        print(result.stdout)
    else:
        print(f"Unsupported platform: {sys.platform}")
