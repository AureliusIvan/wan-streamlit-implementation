"""
Logging Configuration for the WAN Video Application
"""

import logging
import streamlit as st


class StreamlitHandler(logging.Handler):
    """Custom logging handler for Streamlit applications"""
    
    def emit(self, record):
        log_entry = self.format(record)
        
        if record.levelno >= logging.ERROR:
            st.error(f"🔴 {log_entry}")
        elif record.levelno >= logging.WARNING:
            st.warning(f"🟡 {log_entry}")
        elif record.levelno >= logging.INFO:
            if not record.getMessage().startswith('[INTERNAL]'):  # Avoid logging internal messages to UI
                st.info(f"🔵 {log_entry}")
        
        # Always print to standard output for server logs
        print(log_entry)


def setup_logging():
    """Set up logging configuration for the application"""
    logger = logging.getLogger("wan-video")
    
    # Check if handlers are already added to prevent duplicates in Streamlit's hot-reloading
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)

        # Console handler for internal logging
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_format = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s', 
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_format)
        logger.addHandler(console_handler)

        # Streamlit handler for user-facing logs
        streamlit_handler = StreamlitHandler()
        streamlit_handler.setLevel(logging.INFO)
        streamlit_format = logging.Formatter('[%(levelname)s] %(message)s')
        streamlit_handler.setFormatter(streamlit_format)
        logger.addHandler(streamlit_handler)
    
    logger.info('[INTERNAL] Logging configuration initialized')
    return logger