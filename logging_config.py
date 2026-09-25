"""
Logging Configuration Module
Sets up rotating file logging and console logging based on configuration.
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from config import get_config

def setup_logging(app=None):
    """Set up structured logging using values from application config."""
    config = get_config()
    
    log_level_str = config.LOG_LEVEL
    log_level = getattr(logging, log_level_str, logging.INFO)
    
    # Ensure logs directory exists
    log_file = config.LOG_FILE
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    # Formatter configuration
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s [%(pathname)s:%(lineno)d]: %(message)s'
    )
    
    # File Handler
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=config.LOG_MAX_BYTES,
        backupCount=config.LOG_BACKUP_COUNT
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)
    
    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    
    # Root Logger Config
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers
    root_logger.handlers = []
    
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Log startup message
    logging.info(f"Logging initialized with level: {log_level_str} in file: {log_file}")
    
    if app:
        app.logger.handlers = root_logger.handlers
        app.logger.setLevel(log_level)
