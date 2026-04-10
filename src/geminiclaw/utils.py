import logging

class ColorFormatter(logging.Formatter):
    BOLD = "\033[1m"
    RESET = "\033[0m"
    CYAN = "\033[36m"
    COLORS = {
        logging.DEBUG: "\033[34m",
        logging.INFO: "\033[32m",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[35m",
    }

    def __init__(self):
        super().__init__("%(asctime)s - [PID:%(process)d|T:%(thread)d] - %(filename)s:%(lineno)d - %(levelname)s - %(message)s")

    def formatTime(self, record, datefmt=None):
        time_str = super().formatTime(record, datefmt)
        return f"{self.BOLD}{self.CYAN}{time_str}{self.RESET}"

    def format(self, record):
        orig_levelname = record.levelname
        level_color = self.COLORS.get(record.levelno, self.RESET)
        record.levelname = f"{self.BOLD}{level_color}{orig_levelname}{self.RESET}"
        
        result = super().format(record)
        
        record.levelname = orig_levelname
        return result

def setup_logger(name: str) -> logging.Logger:
    """Set up and return a standardized ANSI colored console logger."""
    handler = logging.StreamHandler()
    handler.setFormatter(ColorFormatter())
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        logger.addHandler(handler)
    return logger
