import os
import sys
import subprocess
from pathlib import Path
import shutil

PLIST_LABEL = "com.gemini.claw"
PLIST_FILENAME = f"{PLIST_LABEL}.plist"
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
PLIST_PATH = LAUNCH_AGENTS_DIR / PLIST_FILENAME

def get_uv_path():
    path = shutil.which("uv")
    if not path:
        # Fallback to common locations if not in PATH during execution
        common_paths = [Path.home() / ".cargo" / "bin" / "uv", Path.home() / ".local" / "bin" / "uv"]
        for p in common_paths:
            if p.exists():
                return str(p)
    return path

def install():
    project_dir = Path(__file__).resolve().parent.parent
    uv_path = get_uv_path()
    if not uv_path:
        print("Error: 'uv' executable not found. Please ensure it is installed.")
        sys.exit(1)
        
    # Get the current PATH and proxies to ensure the bot can work correctly when launched by launchd
    env_vars = {
        "PATH": os.environ.get('PATH', '/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin'),
        "HTTP_PROXY": os.environ.get('HTTP_PROXY', ''),
        "HTTPS_PROXY": os.environ.get('HTTPS_PROXY', ''),
        "PYTHONUNBUFFERED": "1",
    }
    
    env_vars_str = "\n".join([f"        <key>{k}</key>\n        <string>{v}</string>" for k, v in env_vars.items() if v])
        
    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{uv_path}</string>
        <string>run</string>
        <string>{project_dir / "src" / "main.py"}</string>
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
    <false/>
</dict>
</plist>
"""
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_text(plist_content)
    print(f"Installed launchd service at {PLIST_PATH}")

def start():
    if not PLIST_PATH.exists():
        print(f"Error: Service not installed at {PLIST_PATH}.")
        print("Please run '/claw setup' or 'uv run src/service.py install' first.")
        sys.exit(1)
        
    print(f"Loading and starting {PLIST_LABEL}...")
    subprocess.run(["launchctl", "load", "-w", str(PLIST_PATH)])
    subprocess.run(["launchctl", "start", PLIST_LABEL])
    print("Service started! Logs are available in claw.log and claw.error.log.")

def stop():
    if not PLIST_PATH.exists():
        print("Service not installed. Nothing to stop.")
        return
        
    print(f"Stopping and unloading {PLIST_LABEL}...")
    subprocess.run(["launchctl", "stop", PLIST_LABEL])
    subprocess.run(["launchctl", "unload", "-w", str(PLIST_PATH)])
    print("Service stopped.")

def status():
    result = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
    found = False
    for line in result.stdout.splitlines():
        if PLIST_LABEL in line:
            print(f"Service status: {line.strip()}")
            found = True
            break
            
    if not found:
        print("Service is not currently loaded or running.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python service.py [install|start|stop|status]")
        sys.exit(1)
        
    command = sys.argv[1]
    if command == "install":
        install()
    elif command == "start":
        start()
    elif command == "stop":
        stop()
    elif command == "status":
        status()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
