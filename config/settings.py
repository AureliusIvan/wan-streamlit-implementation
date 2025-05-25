"""
Application Settings and Configuration Management
"""

import os
import streamlit as st
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv(dotenv_path="./.env.local")

logger = logging.getLogger("wan-video")


def get_api_key():
    """Get API key from environment variable or Streamlit secrets"""
    api_key = os.getenv('DASHSCOPE_API_KEY')
    if not api_key:
        try:
            api_key = st.secrets["DASHSCOPE_API_KEY"]
            logger.info("[INTERNAL] API key loaded from Streamlit secrets.")
        except Exception as e:
            logger.info(f"[INTERNAL] Streamlit secrets not found or DASHSCOPE_API_KEY missing: {e}")
            pass  # Secrets not found or key not in secrets
    
    if api_key:
        logger.info("[INTERNAL] DASHSCOPE_API_KEY is configured.")
    else:
        logger.warning("[INTERNAL] DASHSCOPE_API_KEY is NOT configured.")
    return api_key


def get_r2_credentials():
    """Get Cloudflare R2 credentials from environment variables or Streamlit secrets"""
    credentials = {
        'access_key': os.getenv('R2_ACCESS_KEY_ID'),
        'secret_key': os.getenv('R2_SECRET_ACCESS_KEY'),
        'endpoint_url': os.getenv('R2_ENDPOINT_URL'),
        'bucket_name': os.getenv('R2_BUCKET_NAME'),
        'public_url_base': os.getenv('R2_PUBLIC_URL_BASE')
    }
    
    # Try Streamlit secrets if environment variables are not found
    if not all(credentials.values()):
        try:
            credentials.update({
                'access_key': st.secrets.get("R2_ACCESS_KEY_ID", credentials['access_key']),
                'secret_key': st.secrets.get("R2_SECRET_ACCESS_KEY", credentials['secret_key']),
                'endpoint_url': st.secrets.get("R2_ENDPOINT_URL", credentials['endpoint_url']),
                'bucket_name': st.secrets.get("R2_BUCKET_NAME", credentials['bucket_name']),
                'public_url_base': st.secrets.get("R2_PUBLIC_URL_BASE", credentials['public_url_base'])
            })
            logger.info("[INTERNAL] R2 credentials loaded from Streamlit secrets.")
        except Exception as e:
            logger.info(f"[INTERNAL] Streamlit secrets not found or R2 credentials missing: {e}")
    
    # Check if all required credentials are available
    missing_creds = [key for key, value in credentials.items() if not value]
    if missing_creds:
        logger.warning(f"[INTERNAL] Missing R2 credentials: {missing_creds}")
        return None
    
    logger.info("[INTERNAL] All R2 credentials are configured.")
    return credentials