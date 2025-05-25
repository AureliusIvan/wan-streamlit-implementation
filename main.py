"""
WAN Video Generator - Main Application
Refactored with separation of concerns
"""

import streamlit as st
from PIL import Image

# Import modules from our new structure
from config.logging_config import setup_logging
from config.settings import get_api_key
from constants.api_constants import VIDEO_STYLES
from services.wan_api import (
    create_wan_video_task_with_r2, 
    poll_video_task, 
    generate_image_from_text_with_wan
)
from services.qwen_service import extract_image_description_with_qwen
from ui.components import (
    render_header, 
    render_method_selection, 
    render_style_selector,
    render_image_uploader, 
    render_text_input, 
    render_generate_button,
    render_image_preview, 
    render_sidebar_info
)
from utils.helpers import validate_uploaded_file, display_video_result, display_api_status

# Setup logging
logger = setup_logging()

# Page Configuration
st.set_page_config(
    page_title="WAN Video Generator - AI-Powered Video Creation",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)
logger.info('[INTERNAL] Streamlit page configured')


def generate_video_direct(image_pil, selected_style):
    """Direct image-to-video generation"""
    api_key = get_api_key()
    if not api_key:
        st.error("🔑 API Key Required: Please set your DASHSCOPE_API_KEY environment variable or add it to Streamlit secrets.")
        st.info("To get an API key, visit: https://www.alibabacloud.com/help/en/model-studio/getting-started/get-api-key")
        return None
    
    st.info(f"🎬 Creating video directly from image with style: '{selected_style}'...")
    logger.info(f"Starting direct video generation. Style: {selected_style}")
    
    # Create the video task
    task_response = create_wan_video_task_with_r2(image_pil, selected_style, api_key)
    
    if not task_response:
        logger.error("Task creation failed. No response or error in create_wan_video_task.")
        return None
    
    # Check for task_id in the expected location
    if 'output' not in task_response or 'task_id' not in task_response['output']:
        api_message = task_response.get('message', 'No specific message from API.')
        request_id = task_response.get('request_id', 'N/A')
        st.error(f"Failed to create video generation task. API Message: {api_message} (Request ID: {request_id})")
        st.json(task_response)
        logger.error(f"Task creation response invalid or missing task_id: {task_response}")
        return None
    
    task_id = task_response['output']['task_id']
    st.success(f"✅ Video task created successfully! Task ID: {task_id}")
    logger.info(f"Video task created successfully. Task ID: {task_id}")
    
    # Poll for video generation results
    return poll_video_task(task_id, api_key)


def generate_video_from_text(description, selected_style):
    """Text-to-image-to-video generation"""
    api_key = get_api_key()
    if not api_key:
        st.error("🔑 API Key Required: Please set your DASHSCOPE_API_KEY environment variable or add it to Streamlit secrets.")
        return None
    
    st.info(f"🎯 Starting text-to-image-to-video process...")
    logger.info(f"Starting text-to-image-to-video generation. Style: {selected_style}")
    
    # Step 1: Generate image from text
    generated_image_pil = generate_image_from_text_with_wan(description, api_key)
    if not generated_image_pil:
        st.error("❌ Failed to generate image from text description. Cannot proceed.")
        return None
    
    # Display the generated image
    st.info("📸 Generated image from your description:")
    render_image_preview(generated_image_pil, "AI-generated image from text description")
    
    # Step 2: Generate video from the created image
    return generate_video_direct(generated_image_pil, selected_style)


def generate_video_enhanced(image_pil, selected_style):
    """Image description enhancement to video generation"""
    api_key = get_api_key()
    if not api_key:
        st.error("🔑 API Key Required: Please set your DASHSCOPE_API_KEY environment variable or add it to Streamlit secrets.")
        return None
    
    st.info(f"🎯 Starting three-step enhancement process...")
    logger.info(f"Starting image description enhancement process. Style: {selected_style}")
    
    # Step 1: Extract description from original image
    description = extract_image_description_with_qwen(image_pil, api_key)
    if not description:
        st.error("❌ Failed to extract description from image. Cannot proceed.")
        return None
    
    # Step 2: Generate new image from description
    generated_image_pil = generate_image_from_text_with_wan(description, api_key)
    if not generated_image_pil:
        st.error("❌ Failed to generate enhanced image from description. Cannot proceed.")
        return None
    
    # Display the generated image
    st.info("📸 Enhanced image based on extracted description:")
    render_image_preview(generated_image_pil, "AI-enhanced image from description")
    
    # Step 3: Generate video from the enhanced image
    return generate_video_direct(generated_image_pil, selected_style)


def main():
    """Main application function"""
    # Render header
    render_header()
    
    # Render sidebar information
    render_sidebar_info()
    
    # Check API status
    api_configured, r2_configured = display_api_status()
    
    if not api_configured:
        st.warning("⚠️ API key not configured. Please configure your DASHSCOPE_API_KEY to use the application.")
        st.stop()
    
    # Method selection tabs
    tab1, tab2, tab3 = render_method_selection()
    
    # Initialize session state
    if 'video_result' not in st.session_state:
        st.session_state.video_result = None
    
    # Tab 1: Direct Image-to-Video
    with tab1:
        st.markdown("### 🖼️ Upload an image and generate a video directly")
        
        uploaded_file = render_image_uploader(key="direct_upload")
        image_pil = validate_uploaded_file(uploaded_file)
        
        if image_pil:
            render_image_preview(image_pil, "Uploaded Image")
            
            selected_style = render_style_selector()
            
            if render_generate_button("🎬 Generate Video from Image", key="direct_generate"):
                with st.spinner("🎬 Generating video from your image..."):
                    video_url = generate_video_direct(image_pil, selected_style)
                    if video_url:
                        st.session_state.video_result = video_url
                        display_video_result(video_url)
    
    # Tab 2: Text-to-Image-to-Video
    with tab2:
        st.markdown("### ✍️ Describe an image and generate a video from it")
        
        text_description = render_text_input()
        
        if text_description.strip():
            selected_style = render_style_selector()
            
            if render_generate_button("🎨 Generate Image & Video from Text", key="text_generate"):
                with st.spinner("🎨 Creating image from description and generating video..."):
                    video_url = generate_video_from_text(text_description, selected_style)
                    if video_url:
                        st.session_state.video_result = video_url
                        display_video_result(video_url)
        else:
            st.info("👆 Please enter a description of the image you want to create.")
    
    # Tab 3: Image Description Enhancement
    with tab3:
        st.markdown("### 🔍 Upload an image, extract its description, generate an enhanced version, then create a video")
        
        uploaded_file = render_image_uploader(key="enhance_upload")
        image_pil = validate_uploaded_file(uploaded_file)
        
        if image_pil:
            render_image_preview(image_pil, "Original Image")
            
            selected_style = render_style_selector()
            
            if render_generate_button("🚀 Extract, Enhance & Generate Video", key="enhance_generate"):
                with st.spinner("🚀 Extracting description, creating enhanced image, and generating video..."):
                    video_url = generate_video_enhanced(image_pil, selected_style)
                    if video_url:
                        st.session_state.video_result = video_url
                        display_video_result(video_url)
    
    # Display persistent video result
    if st.session_state.video_result:
        st.markdown("---")
        st.markdown("### 🎉 Latest Generated Video")
        display_video_result(st.session_state.video_result)
    
    # Footer
    st.markdown("---")
    st.markdown("🤖 Powered by **Alibaba Cloud WAN (万相) - wanx-i2v model**. Advanced AI for image-to-video generation.")
    
    # Setup instructions
    with st.expander("📋 Setup & Troubleshooting", expanded=False):
        st.markdown("""
        **To use this application with Alibaba Cloud API:**
        
        1. **Get API Access:**
           * Visit [Alibaba Cloud Model Studio](https://www.alibabacloud.com/help/en/model-studio/getting-started/get-api-key)
           * Activate DashScope and obtain your `DASHSCOPE_API_KEY`
           * Ensure video generation services are enabled with sufficient quota
        
        2. **Set API Key:**
           * Create `.streamlit/secrets.toml` with: `DASHSCOPE_API_KEY = "your-key"`
           * Or set environment variable: `DASHSCOPE_API_KEY="your-key"`
        
        3. **Optional - Configure Cloudflare R2:**
           * For better performance, configure R2 storage credentials
           * Add R2 credentials to environment or Streamlit secrets
        
        4. **Run the application:**
           ```bash
           streamlit run main.py
           ```
        
        **Troubleshooting:**
        * Check API key permissions and quota in Alibaba Cloud console
        * Try different images or styles if generation fails
        * Video generation can take 5-15 minutes depending on queue
        * Monitor logs for detailed error information
        """)


if __name__ == "__main__":
    main()
