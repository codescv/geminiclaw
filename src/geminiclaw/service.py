import os
import sys
import subprocess
from pathlib import Path
import shutil

LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
SYSTEMD_USER_DIR = Path.home() / ".config" / "systemd" / "user"

ENV_VARS = [
    'HTTP_PROXY', 'HTTPS_PROXY', 
    'GOOGLE_API_KEY', 'GOOGLE_CLOUD_PROJECT', 'GOOGLE_CLOUD_LOCATION',
    'GOOGLE_GENAI_USE_VERTEXAI', 'DISCORD_TOKEN'
]

def get_macos_paths(service_name):
    plist_label = service_name
    plist_filename = f"{plist_label}.plist"
    plist_path = LAUNCH_AGENTS_DIR / plist_filename
    return plist_label, plist_path

def get_linux_paths(service_name):
    systemd_service_name = f"{service_name}.service"
    systemd_service_path = SYSTEMD_USER_DIR / systemd_service_name
    return systemd_service_name, systemd_service_path

def get_executable_path(executable_name):
    path = shutil.which(executable_name)
    if not path:
        # Fallback to common locations if not in PATH during execution
        common_paths = [Path.home() / ".cargo" / "bin" / executable_name, Path.home() / ".local" / "bin" / executable_name]
        for p in common_paths:
            if p.exists():
                return str(p)
    return path

def install_macos(project_dir, geminiclaw_path, env_vars, service_name):
    plist_label, plist_path = get_macos_paths(service_name)
    env_vars_str = "\n".join([f"        <key>{k}</key>\n        <string>{v}</string>" for k, v in env_vars.items() if v])
    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{plist_label}</string>
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
    plist_path.write_text(plist_content)
    print(f"Installed launchd service at {plist_path}")

def install_linux(project_dir, geminiclaw_path, env_vars, service_name):
    systemd_service_name, systemd_service_path = get_linux_paths(service_name)
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
    systemd_service_path.write_text(service_content)
    subprocess.run(["systemctl", "--user", "daemon-reload"])
    subprocess.run(["systemctl", "--user", "enable", systemd_service_name])
    print(f"Installed systemd service at {systemd_service_path}")

def install(service_name="com.codescv.geminiclaw"):
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
        install_macos(project_dir, geminiclaw_path, env_vars, service_name)
    elif sys.platform == "linux":
        install_linux(project_dir, geminiclaw_path, env_vars, service_name)
    else:
        print(f"Unsupported platform: {sys.platform}")
        sys.exit(1)

def start(service_name="com.codescv.geminiclaw"):
    if sys.platform == "darwin":
        plist_label, plist_path = get_macos_paths(service_name)
        if not plist_path.exists():
            print(f"Error: Service not installed at {plist_path}.")
            print("Please run 'geminiclaw service install --service-name {service_name}' first.")
            sys.exit(1)
            
        print(f"Loading and starting {plist_label}...")
        subprocess.run(["launchctl", "load", "-w", str(plist_path)])
        subprocess.run(["launchctl", "start", plist_label])
        print("Service started! Logs are available in claw.log and claw.error.log.")
    elif sys.platform == "linux":
        systemd_service_name, systemd_service_path = get_linux_paths(service_name)
        if not systemd_service_path.exists():
            print(f"Error: Service not installed at {systemd_service_path}.")
            print("Please run 'geminiclaw service install --service-name {service_name}' first.")
            sys.exit(1)
            
        print(f"Starting {systemd_service_name}...")
        subprocess.run(["systemctl", "--user", "start", systemd_service_name])
        print("Service started! Logs are available in claw.log and claw.error.log.")
    else:
        print(f"Unsupported platform: {sys.platform}")
        sys.exit(1)

def stop(service_name="com.codescv.geminiclaw"):
    if sys.platform == "darwin":
        plist_label, plist_path = get_macos_paths(service_name)
        if not plist_path.exists():
            print("Service not installed. Nothing to stop.")
            return
            
        print(f"Stopping and unloading {plist_label}...")
        subprocess.run(["launchctl", "stop", plist_label])
        subprocess.run(["launchctl", "unload", "-w", str(plist_path)])
        print("Service stopped.")
    elif sys.platform == "linux":
        systemd_service_name, systemd_service_path = get_linux_paths(service_name)
        if not systemd_service_path.exists():
            print("Service not installed. Nothing to stop.")
            return
            
        print(f"Stopping and disabling {systemd_service_name}...")
        subprocess.run(["systemctl", "--user", "stop", systemd_service_name])
        subprocess.run(["systemctl", "--user", "disable", systemd_service_name])
        print("Service stopped.")
    else:
        print(f"Unsupported platform: {sys.platform}")

def status(service_name="com.codescv.geminiclaw"):
    if sys.platform == "darwin":
        plist_label, _ = get_macos_paths(service_name)
        result = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
        found = False
        for line in result.stdout.splitlines():
            if plist_label in line:
                print(f"Service status: {line.strip()}")
                found = True
                break
                
        if not found:
            print("Service is not currently loaded or running.")
    elif sys.platform == "linux":
        systemd_service_name, _ = get_linux_paths(service_name)
        result = subprocess.run(["systemctl", "--user", "status", systemd_service_name], capture_output=True, text=True)
        print(result.stdout)
    else:
        print(f"Unsupported platform: {sys.platform}")
