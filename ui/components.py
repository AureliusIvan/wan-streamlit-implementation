"""
Streamlit UI Components
"""

import streamlit as st
from constants.api_constants import VIDEO_STYLES


def render_header():
    """Render the application header"""
    st.title("🎬 WAN Video Generator")
    st.markdown("""
    **Transform your images into captivating videos using AI!**
    
    This app provides three powerful methods:
    1. **Direct Image-to-Video**: Upload an image and generate a video directly
    2. **Text-to-Image-to-Video**: Create an image from text, then generate a video
    3. **Image Description Enhancement**: Extract description from your image, generate a new enhanced image, then create a video
    """)


def render_method_selection():
    """Render method selection tabs"""
    tab1, tab2, tab3 = st.tabs([
        "🖼️ Direct Image-to-Video", 
        "✍️ Text-to-Image-to-Video", 
        "🔍 Image Description Enhancement"
    ])
    return tab1, tab2, tab3


def render_style_selector():
    """Render video style selector"""
    return st.selectbox(
        "🎨 Select Video Style:",
        VIDEO_STYLES,
        index=0,
        help="Choose the artistic style for your video. '<auto>' lets the AI decide the best style."
    )


def render_image_uploader(key=None):
    """Render image file uploader"""
    return st.file_uploader(
        "📁 Upload an image:",
        type=["png", "jpg", "jpeg"],
        key=key,
        help="Upload a clear, high-quality image for best results."
    )


def render_text_input():
    """Render text input for description"""
    return st.text_area(
        "✍️ Describe the image you want to create:",
        placeholder="E.g., A delicious chocolate cake with strawberries on a wooden table, warm lighting, professional food photography",
        height=100,
        help="Be descriptive! Include details about the subject, colors, setting, and style you want."
    )


def render_generate_button(text="🎬 Generate Video", key=None):
    """Render generate button"""
    return st.button(text, type="primary", key=key, use_container_width=True)


def render_image_preview(image, caption="Uploaded Image"):
    """Render image preview"""
    if image:
        st.image(image, caption=caption, use_column_width=True)


def render_sidebar_info():
    """Render sidebar information"""
    with st.sidebar:
        st.markdown("### ℹ️ How it works")
        st.markdown("""
        **Method 1: Direct Image-to-Video**
        - Upload your image
        - Choose a style
        - Generate video directly
        
        **Method 2: Text-to-Image-to-Video**
        - Describe your desired image
        - AI creates the image
        - Generate video from created image
        
        **Method 3: Image Description Enhancement**
        - Upload an image
        - AI extracts detailed description
        - Generate enhanced image from description
        - Create video from enhanced image
        """)
        
        st.markdown("### ⚙️ Configuration")
        from utils.helpers import display_api_status
        display_api_status()
        
        st.markdown("### 💡 Tips")
        st.markdown("""
        - Use high-quality, clear images
        - Try different styles for variety
        - Be descriptive in text prompts
        - Processing can take 5-10 minutes
        """)


def render_processing_status():
    """Render processing status indicators"""
    st.markdown("---")
    st.markdown("### 🔄 Processing Status")
    return st.empty()  # Placeholder for dynamic status updates