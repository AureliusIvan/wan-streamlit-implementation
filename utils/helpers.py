"""
Utility Helper Functions
"""

import logging
from PIL import Image
import streamlit as st

from constants.api_constants import SUPPORTED_IMAGE_TYPES

logger = logging.getLogger("wan-video")


def validate_uploaded_file(uploaded_file):
    """Validate uploaded file type and convert to PIL Image"""
    if uploaded_file is not None:
        # Check file extension
        file_extension = uploaded_file.name.split('.')[-1].lower()
        if file_extension not in SUPPORTED_IMAGE_TYPES:
            st.error(f"❌ Unsupported file type: {file_extension}. Please upload a {', '.join(SUPPORTED_IMAGE_TYPES)} file.")
            return None
        
        try:
            # Convert uploaded file to PIL Image
            image = Image.open(uploaded_file)
            logger.info(f"[INTERNAL] Image loaded: {image.size}, mode: {image.mode}")
            return image
        except Exception as e:
            st.error(f"❌ Failed to process image: {str(e)}")
            logger.error(f"Failed to process uploaded image: {str(e)}")
            return None
    return None


def display_video_result(video_url):
    """Display video result with download option"""
    if video_url:
        st.success("🎉 Video generated successfully!")
        
        # Display the video
        try:
            st.video(video_url)
        except Exception as e:
            st.error(f"Failed to display video: {str(e)}")
            logger.error(f"Failed to display video: {str(e)}")
        
        # Provide download link
        st.markdown(f"**[📥 Download Video]({video_url})**")
        
        # Show the URL for reference
        with st.expander("🔗 Video URL"):
            st.code(video_url)
        
        logger.info(f"Video result displayed: {video_url}")


def display_api_status():
    """Display API configuration status"""
    from config.settings import get_api_key, get_r2_credentials
    
    api_key = get_api_key()
    r2_creds = get_r2_credentials()
    
    col1, col2 = st.columns(2)
    
    with col1:
        if api_key:
            st.success("✅ DashScope API Key configured")
        else:
            st.error("❌ DashScope API Key missing")
            st.info("Please configure DASHSCOPE_API_KEY in your environment or Streamlit secrets.")
    
    with col2:
        if r2_creds:
            st.success("✅ Cloudflare R2 configured")
        else:
            st.warning("⚠️ Cloudflare R2 not configured")
            st.info("R2 configuration is optional but recommended for better performance.")
    
    return bool(api_key), bool(r2_creds)