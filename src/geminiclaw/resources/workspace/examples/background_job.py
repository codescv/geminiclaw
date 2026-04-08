import time
from datetime import datetime

def run_background_job():
    log_file = "/tmp/bg_task_example.log"
    message = "Background task running and writing a sentence."
    
    with open(log_file, "a") as f:
        f.write(f"--- Job started at {datetime.now().isoformat()} ---\n")
    
    for _ in range(360):
        with open(log_file, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] {message}\n")
        time.sleep(10)
        
    with open(log_file, "a") as f:
        f.write(f"--- Job finished at {datetime.now().isoformat()} ---\n")

if __name__ == "__main__":
    run_background_job()
