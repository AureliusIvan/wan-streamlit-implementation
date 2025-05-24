import streamlit as st
from PIL import Image
import time
import os
import requests
import json
import base64
from io import BytesIO
from dotenv import load_dotenv
import logging
import datetime
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import uuid

# Configure logging
class StreamlitHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        
        if record.levelno >= logging.ERROR:
            st.error(f"🔴 {log_entry}")
        elif record.levelno >= logging.WARNING:
            st.warning(f"🟡 {log_entry}")
        elif record.levelno >= logging.INFO:
            if not record.getMessage().startswith('[INTERNAL]'): # Avoid logging internal messages to UI
                st.info(f"🔵 {log_entry}")
        
        # Always print to standard output for server logs
        print(log_entry)

# Create logger
logger = logging.getLogger("wan-video")
# Check if handlers are already added to prevent duplicates in Streamlit's hot-reloading
if not logger.handlers:
    logger.setLevel(logging.DEBUG)

    # Console handler for internal logging
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_format = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', 
                                     datefmt='%Y-%m-%d %H:%M:%S')
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # Streamlit handler for user-facing logs
    streamlit_handler = StreamlitHandler()
    streamlit_handler.setLevel(logging.INFO)
    streamlit_format = logging.Formatter('[%(levelname)s] %(message)s')
    streamlit_handler.setFormatter(streamlit_format)
    logger.addHandler(streamlit_handler)

# Load environment variables from .env file
load_dotenv(dotenv_path="./.env.local")
logger.info('[INTERNAL] Environment variables loaded (if .env exists)')

# --- Page Configuration ---
st.set_page_config(
    page_title="Appetizing Food Video Generator (Image-to-Video)",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)
logger.info('[INTERNAL] Streamlit page configured')

# --- API Configuration ---
WAN_API_BASE_URL = "https://dashscope-intl.aliyuncs.com/api/v1"
# This endpoint is for submitting video synthesis tasks
WAN_VIDEO_ENDPOINT = f"{WAN_API_BASE_URL}/services/aigc/video-generation/video-synthesis"
# This endpoint is for text-to-image generation
WAN_TEXT_TO_IMAGE_ENDPOINT = f"{WAN_API_BASE_URL}/services/aigc/text2image/image-synthesis"
# This endpoint is for image-to-text extraction using Qwen VL
QWEN_VL_ENDPOINT = f"{WAN_API_BASE_URL}/services/aigc/multimodal-generation/generation"
# This endpoint is for checking task status
WAN_TASK_ENDPOINT = f"{WAN_API_BASE_URL}/tasks"
logger.debug(f'[INTERNAL] API video endpoint configured: {WAN_VIDEO_ENDPOINT}')
logger.debug(f'[INTERNAL] API text-to-image endpoint configured: {WAN_TEXT_TO_IMAGE_ENDPOINT}')
logger.debug(f'[INTERNAL] API task endpoint configured: {WAN_TASK_ENDPOINT}')


def get_api_key():
    """Get API key from environment variable or Streamlit secrets"""
    api_key = os.getenv('DASHSCOPE_API_KEY')
    if not api_key:
        try:
            api_key = st.secrets["DASHSCOPE_API_KEY"]
            logger.info("[INTERNAL] API key loaded from Streamlit secrets.")
        except Exception as e:
            logger.info(f"[INTERNAL] Streamlit secrets not found or DASHSCOPE_API_KEY missing: {e}")
            pass # Secrets not found or key not in secrets
    
    if api_key:
        logger.info("[INTERNAL] DASHSCOPE_API_KEY is configured.")
    else:
        logger.warning("[INTERNAL] DASHSCOPE_API_KEY is NOT configured.")
    return api_key

# --- Cloudflare R2 Storage Functions ---
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

def create_r2_client():
    """Create a boto3 S3 client configured for Cloudflare R2"""
    credentials = get_r2_credentials()
    if not credentials:
        return None
    
    try:
        client = boto3.client(
            's3',
            aws_access_key_id=credentials['access_key'],
            aws_secret_access_key=credentials['secret_key'],
            endpoint_url=credentials['endpoint_url'],
            region_name='auto'  # Cloudflare R2 uses 'auto' region
        )
        logger.info("[INTERNAL] R2 S3 client created successfully.")
        return client, credentials
    except Exception as e:
        logger.error(f"[INTERNAL] Failed to create R2 client: {e}")
        return None

def upload_image_to_r2(image_pil):
    """Upload PIL image to Cloudflare R2 and return public URL"""
    try:
        r2_setup = create_r2_client()
        if not r2_setup:
            logger.error("Failed to create R2 client. Check R2 credentials.")
            return None
        
        client, credentials = r2_setup
        
        # Prepare image for upload
        if image_pil.mode != 'RGB':
            image_pil = image_pil.convert('RGB')
        
        # Resize image if too large
        max_size = 1024
        if max(image_pil.size) > max_size:
            image_pil.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            logger.info(f"[INTERNAL] Image resized to {image_pil.size} for R2 upload.")
        
        # Convert to bytes
        buffered = BytesIO()
        image_pil.save(buffered, format="JPEG", quality=85)
        image_bytes = buffered.getvalue()
        
        # Generate unique filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"wan-images/{timestamp}_{unique_id}.jpg"
        
        # Upload to R2
        client.put_object(
            Bucket=credentials['bucket_name'],
            Key=filename,
            Body=image_bytes,
            ContentType='image/jpeg',
            CacheControl='max-age=86400'  # 24 hours cache
        )
        
        # Construct public URL
        public_url = f"{credentials['public_url_base']}/{filename}"
        logger.info(f"[INTERNAL] Image uploaded to R2: {public_url}")
        return public_url
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        logger.error(f"R2 ClientError: {error_code} - {error_message}")
        st.error(f"Failed to upload image to R2: {error_code} - {error_message}")
        return None
    except NoCredentialsError:
        logger.error("R2 credentials not found or invalid.")
        st.error("R2 credentials not found. Please check your configuration.")
        return None
    except Exception as e:
        logger.error(f"Unexpected error uploading to R2: {str(e)}")
        st.error(f"Failed to upload image to R2: {str(e)}")
        return None

def create_wan_video_task_with_r2(image_pil, selected_style, api_key):
    """Create an image-to-video generation task using WAN API with R2-hosted image"""
    # First upload image to R2
    st.info("📤 Uploading image to cloud storage...")
    image_url = upload_image_to_r2(image_pil)
    
    if not image_url:
        st.error("Failed to upload image to cloud storage. Cannot proceed with video generation.")
        return None
    
    st.success(f"✅ Image uploaded successfully!")
    logger.info(f"Image uploaded to R2, proceeding with WAN API call. URL: {image_url}")
    
    headers = {
        'X-DashScope-Async': 'enable',
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    # Updated payload structure based on your curl example
    payload = {
        "model": "wan2.1-i2v-turbo",  # Using the model from your curl example
        "input": {
            "prompt": "An appetizing food",
            "img_url": image_url  # Use the R2 URL instead of base64
        },
        "parameters": {
            "resolution": "720P",  # Using the structure from your curl example
            "prompt_extend": True
        }
    }
    
    # Add style parameter if not auto
    if selected_style != "<auto>":
        payload["parameters"]["style"] = selected_style

    logger.info(f"Creating image-to-video task with model: {payload['model']}, style: {selected_style}")
    logger.debug(f"[INTERNAL] Payload: {json.dumps(payload, indent=2)}")
    
    # Add retry logic for transient errors
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(WAN_VIDEO_ENDPOINT, headers=headers, json=payload, timeout=30)
            response_json = None
            
            try:
                response_json = response.json()
                logger.debug(f"[INTERNAL] API Raw Response (attempt {attempt + 1}): {response.status_code} - {response.text}")
            except json.JSONDecodeError:
                logger.error(f"[INTERNAL] API response was not valid JSON: {response.text}")
                st.error(f"API Error: Received non-JSON response from server (Status: {response.status_code}). Check logs.")
                return None
            
            response.raise_for_status()
            logger.info(f"Video task creation request successful: {response_json}")
            return response_json
            
        except requests.exceptions.HTTPError as http_err:
            if response_json and response_json.get('output', {}).get('code') == 'InternalError':
                logger.warning(f"InternalError on attempt {attempt + 1}/{max_retries}: {response_json.get('output', {}).get('message', 'Unknown')}")
                
                if attempt == max_retries - 1:  # Last attempt
                    st.error("""
                    🔴 **API Internal Server Error**
                    
                    The Alibaba Cloud WAN service is experiencing internal issues. This is typically a temporary server-side problem.
                    
                    **What you can try:**
                    1. **Wait a few minutes** and try again - server issues are often temporary
                    2. **Try a different image** - some images may trigger processing errors
                    3. **Use a simpler style** like '<auto>' instead of specific styles
                    4. **Reduce image complexity** - try a clearer, simpler food image
                    5. **Check your API quota** in the Alibaba Cloud console
                    
                    **Technical Details:**
                    - Error Code: InternalError
                    - Message: submit algo service error, Internal server error!
                    - This suggests a server-side processing issue, not a client-side problem
                    """)
                    return response_json
                else:
                    st.warning(f"Server error on attempt {attempt + 1}, retrying in 3 seconds...")
                    time.sleep(3)  # Wait before retry
                    continue
            else:
                error_msg = f"HTTP error occurred: {http_err}"
                if response_json and 'message' in response_json:
                    error_msg += f" - API Message: {response_json['message']}"
                elif response_json and 'output' in response_json and 'message' in response_json['output']:
                    error_msg += f" - API Output Message: {response_json['output']['message']}"
                st.error(f"API Request Failed: {error_msg}")
                logger.error(f"API request failed: {error_msg} - Response: {response_json}")
                return response_json
                
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                error_msg = str(e)
                st.error(f"API request failed after {max_retries} attempts: {error_msg}")
                logger.error(f"API request failed: {error_msg}")
                return None
            else:
                logger.warning(f"Request exception on attempt {attempt + 1}, retrying: {str(e)}")
                time.sleep(2)
                continue
    
    return None
def check_task_status(task_id, api_key):
    """Check the status of a video generation task"""
    headers = {
        'Authorization': f'Bearer {api_key}'
    }
    
    task_url = f"{WAN_TASK_ENDPOINT}/{task_id}"
    logger.debug(f"[INTERNAL] Checking task status for URL: {task_url}")

    try:
        response = requests.get(task_url, headers=headers)
        response_json = None
        
        try:
            response_json = response.json()
            logger.debug(f"[INTERNAL] Task Status Raw Response: {response.status_code} - {response.text}")
        except json.JSONDecodeError:
            logger.error(f"[INTERNAL] Task status response was not valid JSON: {response.text}")
            st.error(f"API Error: Received non-JSON response while checking task status (Status: {response.status_code}).")
            return None

        response.raise_for_status()
        logger.info(f"Task status checked successfully: {response_json}")
        return response_json
    except requests.exceptions.HTTPError as http_err:
        error_msg = f"HTTP error occurred while checking task status: {http_err}"
        if response_json and 'message' in response_json:
            error_msg += f" - API Message: {response_json['message']}"
        st.error(f"Failed to check task status: {error_msg}")
        logger.error(f"Failed to check task status: {error_msg} - Response: {response_json}")
        return response_json 
    except requests.exceptions.RequestException as e:
        error_msg = str(e)
        st.error(f"Failed to check task status: {error_msg}")
        logger.error(f"Failed to check task status: {error_msg}")
        return None

def generate_video_with_wan(image_pil, selected_style):
    """
    Generate video using the three-step process:
    1. Extract description from original image using Qwen VL
    2. Generate new image from description using WAN text-to-image
    3. Generate video from new image using WAN image-to-video
    """
    api_key = get_api_key()
    if not api_key:
        st.error("🔑 API Key Required: Please set your DASHSCOPE_API_KEY environment variable or add it to Streamlit secrets.")
        st.info("To get an API key, visit: https://www.alibabacloud.com/help/en/model-studio/getting-started/get-api-key")
        logger.warning("API key not found. User prompted to set API key.")
        return None
    
    # Step 1: Extract description from original image
    st.info(f"🎯 Starting three-step process to generate video...")
    logger.info(f"Starting three-step video generation process. Style: {selected_style}")
    
    description = extract_image_description_with_qwen(image_pil, api_key)
    if not description:
        st.error("❌ Failed to extract description from image. Cannot proceed.")
        return None
    
    # Step 2: Generate new image from description
    generated_image_pil = generate_image_from_text_with_wan(description, api_key)
    if not generated_image_pil:
        st.error("❌ Failed to generate new image from description. Cannot proceed.")
        return None
    
    # Display the generated image for user feedback
    st.info("📸 Generated image based on description:")
    st.image(generated_image_pil, caption="AI-generated image from description", use_column_width=True)
    
    # Step 3: Generate video from the new generated image
    st.info(f"🎬 Creating video from generated image with style: '{selected_style}'...")
    logger.info(f"Creating video from generated image. Style: {selected_style}")
    
    # Create the video task using the generated image
    task_response = create_wan_video_task_with_r2(generated_image_pil, selected_style, api_key)
    
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
    st.info("🔄 Processing video... This may take 5-10 minutes depending on queue.")
    logger.info(f"Polling for video task status (Task ID: {task_id})...")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    max_attempts = 180 
    poll_interval_seconds = 5
    
    for attempt in range(max_attempts):
        progress = min((attempt + 1) / max_attempts, 0.95)
        progress_bar.progress(progress)
        
        status_text.text(f"Checking video status... (Attempt {attempt + 1}/{max_attempts})")
        logger.info(f"Polling attempt {attempt + 1}/{max_attempts} for video task {task_id}")
        
        time.sleep(poll_interval_seconds)
        
        result = check_task_status(task_id, api_key)
        if not result:
            logger.warning(f"Attempt {attempt + 1}: Failed to get task status or received null result. Retrying...")
            if attempt == max_attempts - 1:
                 st.error("Failed to retrieve task status after multiple attempts.")
                 return None
            continue
        
        task_status = result.get('output', {}).get('task_status', 'UNKNOWN')
        logger.info(f"Video task {task_id} status at attempt {attempt + 1}: {task_status}")
        
        if task_status == 'SUCCEEDED':
            progress_bar.progress(1.0)
            status_text.success("✅ Video generation completed!")
            logger.info(f"Video task {task_id} SUCCEEDED.")
            
            video_url = result.get('output', {}).get('video_url')
            if video_url:
                st.success("🎉 Video generated successfully using three-step process!")
                logger.info(f"Video URL for task {task_id}: {video_url}")
                return video_url
            else:
                st.error("Video generation completed but no video_url returned in response.")
                st.json(result)
                logger.error(f"Video generation for task {task_id} succeeded but no video_url found in response: {result}")
                return None
                
        elif task_status == 'FAILED':
            error_message = result.get('output', {}).get('message', 'Unknown error')
            code = result.get('output', {}).get('code', 'N/A')
            st.error(f"❌ Video generation failed. Status: {task_status}, Code: {code}, Message: {error_message}")
            st.json(result)
            logger.error(f"Video generation for task {task_id} FAILED: {error_message}. Full response: {result}")
            
            if "InternalError.Algo" in error_message or "AlgoError" in code:
                st.warning("""
                **What happened?**
                The AI model encountered an internal algorithmic error processing your generated image.
                
                **Suggestions to fix this:**
                1. Try a different original image (higher quality or clearer subject).
                2. Ensure the original image is suitable for the selected style.
                3. Try the '<auto>' style.
                """)
            elif "Quota" in code or "LimitExceeded" in code or "QPS" in error_message:
                st.warning("""
                You've likely reached an API rate limit or quota for video generation. 
                Please check your Alibaba Cloud console for quota details and wait before trying again.
                """)
            else:
                 st.info("Consider trying a different image, style, or checking the Alibaba Cloud console for more details if errors persist.")
            return None
            
        elif task_status in ['PENDING', 'RUNNING']:
            status_text.info(f"🔄 Status: {task_status} - Please wait...")
            logger.info(f"Video task {task_id} still in progress: {task_status}")
        else:
            status_text.warning(f"⏳ Status: {task_status} - Processing...")
            logger.info(f"Video task {task_id} status: {task_status}")
            if task_status == 'UNKNOWN' and attempt > 10:
                logger.warning(f"Video task {task_id} status is UNKNOWN for multiple attempts. There might be an issue.")
    
    st.error("⏰ Video generation timed out after several attempts. Please try again later or check the task status on Alibaba Cloud console.")
    logger.error(f"Video generation for task {task_id} timed out after {max_attempts} attempts.")
    return None

# --- Helper Functions (Mock) ---
def generate_mock_video(image_pil, style_name):
    """
    MOCK FUNCTION: Simulates image-to-video generation.
    Kept for fallback or testing without API calls.
    """
    st.info(f"Simulating video generation for image with style: '{style_name}'...")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    for percent_complete in range(100):
        time.sleep(0.03)  # Simulate work
        progress_bar.progress(percent_complete + 1)
        status_text.text(f"Simulating... {percent_complete+1}%")
    
    # Create a dummy file to represent the video
    # Using a timestamp in the filename to make it unique
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    mock_video_filename = f"mock_video_{timestamp}_{style_name.replace('<','').replace('>','')}.mp4"
    
    # Create a tiny, valid MP4 file for testing purposes if possible, otherwise just a text file.
    # For simplicity, we'll create a text file.
    try:
        with open(mock_video_filename, "w") as f:
            f.write(f"This is a mock video file for style '{style_name}' generated from an image.")
        st.success("Mock video generation complete! (This is a simulation)")
        logger.info(f"Mock video generated: {mock_video_filename}")
        return mock_video_filename # Return the path to the mock video file
    except Exception as e:
        st.error(f"Failed to create mock video file: {e}")
        logger.error(f"Failed to create mock video file: {e}")
        return None

def extract_image_description_with_qwen(image_pil, api_key):
    """Extract description from image using Qwen VL model"""
    # First upload image to R2
    st.info("📝 Analyzing image to extract description...")
    image_url = upload_image_to_r2(image_pil)
    
    if not image_url:
        st.error("Failed to upload image to cloud storage for description extraction.")
        return None
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    # Payload structure for Qwen VL
    payload = {
        "model": "qwen-vl-plus-latest",
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "image": image_url
                        },
                        {
                            "text": "Please describe this image in detail, focusing on the main subject, colors, composition, style, and any important visual elements. Provide a comprehensive description suitable for image generation."
                        }
                    ]
                }
            ]
        }
    }
    
    logger.info(f"Extracting image description using Qwen VL model")
    logger.debug(f"[INTERNAL] Qwen VL Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(QWEN_VL_ENDPOINT, headers=headers, json=payload, timeout=60)
        response_json = None
        
        try:
            response_json = response.json()
            logger.debug(f"[INTERNAL] Qwen VL Raw Response: {response.status_code} - {response.text}")
        except json.JSONDecodeError:
            logger.error(f"[INTERNAL] Qwen VL response was not valid JSON: {response.text}")
            st.error(f"API Error: Received non-JSON response from Qwen VL (Status: {response.status_code})")
            return None
        
        response.raise_for_status()
        
        # Extract description from response - handle the correct structure
        if 'output' in response_json and 'choices' in response_json['output'] and len(response_json['output']['choices']) > 0:
            choices = response_json['output']['choices'][0]
            if 'message' in choices and 'content' in choices['message']:
                content = choices['message']['content']
                
                # Handle the case where content is an array of objects with 'text' key
                if isinstance(content, list) and len(content) > 0:
                    # Find the first text content in the array
                    for item in content:
                        if isinstance(item, dict) and 'text' in item:
                            description = item['text']
                            st.success(f"✅ Image description extracted: {description[:100]}...")
                            logger.info(f"Image description extracted successfully: {description}")
                            return description
                    
                    # If no text found in array items, log the structure
                    st.error("No text content found in Qwen VL response array")
                    logger.error(f"No text content found in Qwen VL response content array: {content}")
                    return None
                
                # Handle the case where content is a direct string (fallback)
                elif isinstance(content, str):
                    description = content
                    st.success(f"✅ Image description extracted: {description[:100]}...")
                    logger.info(f"Image description extracted successfully: {description}")
                    return description
                
                else:
                    st.error("Unexpected content structure in Qwen VL response")
                    logger.error(f"Unexpected content structure in Qwen VL response: {type(content)} - {content}")
                    return None
            else:
                st.error("Missing message or content in Qwen VL response")
                logger.error(f"Missing message or content in Qwen VL response: {choices}")
                return None
        else:
            st.error("No choices found in Qwen VL response")
            logger.error(f"No choices found in Qwen VL response: {response_json}")
            return None
            
    except requests.exceptions.HTTPError as http_err:
        error_msg = f"HTTP error occurred while extracting description: {http_err}"
        if response_json and 'message' in response_json:
            error_msg += f" - API Message: {response_json['message']}"
        st.error(f"Failed to extract image description: {error_msg}")
        logger.error(f"Failed to extract image description: {error_msg} - Response: {response_json}")
        return None
    except requests.exceptions.RequestException as e:
        error_msg = str(e)
        st.error(f"Failed to extract image description: {error_msg}")
        logger.error(f"Failed to extract image description: {error_msg}")
        return None

def generate_image_from_text_with_wan(description, api_key):
    """Generate image from text description using WAN text-to-image model"""
    st.info("🎨 Generating new image from description...")
    
    headers = {
        'X-DashScope-Async': 'enable',
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    # Payload structure for WAN text-to-image
    payload = {
        "model": "wan2.1-t2i-turbo",
        "input": {
            "prompt": description,
            "negative_prompt": "low quality, blurry, distorted"
        },
        "parameters": {
            "size": "1024*1024",
            "n": 1
        }
    }
    
    logger.info(f"Generating image from description using WAN text-to-image model")
    logger.debug(f"[INTERNAL] WAN T2I Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(WAN_TEXT_TO_IMAGE_ENDPOINT, headers=headers, json=payload, timeout=30)
        response_json = None
        
        try:
            response_json = response.json()
            logger.debug(f"[INTERNAL] WAN T2I Raw Response: {response.status_code} - {response.text}")
        except json.JSONDecodeError:
            logger.error(f"[INTERNAL] WAN T2I response was not valid JSON: {response.text}")
            st.error(f"API Error: Received non-JSON response from WAN T2I (Status: {response.status_code})")
            return None
        
        response.raise_for_status()
        
        # Check for task_id in the response
        if 'output' not in response_json or 'task_id' not in response_json['output']:
            api_message = response_json.get('message', 'No specific message from API.')
            st.error(f"Failed to create image generation task. API Message: {api_message}")
            logger.error(f"Image generation task creation response invalid: {response_json}")
            return None
        
        task_id = response_json['output']['task_id']
        st.success(f"✅ Image generation task created! Task ID: {task_id}")
        logger.info(f"Image generation task created successfully. Task ID: {task_id}")
        
        # Poll for results
        st.info("🔄 Processing image generation...")
        max_attempts = 60  # 60 attempts * 3s = 3 minutes
        poll_interval_seconds = 3
        
        for attempt in range(max_attempts):
            time.sleep(poll_interval_seconds)
            
            result = check_task_status(task_id, api_key)
            if not result:
                continue
            
            task_status = result.get('output', {}).get('task_status', 'UNKNOWN')
            logger.info(f"Image generation task {task_id} status: {task_status}")
            
            if task_status == 'SUCCEEDED':
                # Extract image URL from result
                if 'results' in result.get('output', {}) and len(result['output']['results']) > 0:
                    image_url = result['output']['results'][0].get('url')
                    if image_url:
                        st.success("🎉 Image generated successfully!")
                        logger.info(f"Image generated successfully: {image_url}")
                        
                        # Download the generated image and convert to PIL
                        try:
                            img_response = requests.get(image_url, timeout=30)
                            img_response.raise_for_status()
                            generated_image_pil = Image.open(BytesIO(img_response.content))
                            return generated_image_pil
                        except Exception as e:
                            st.error(f"Failed to download generated image: {str(e)}")
                            logger.error(f"Failed to download generated image: {str(e)}")
                            return None
                    else:
                        st.error("Image generation completed but no image URL found")
                        return None
                else:
                    st.error("Image generation completed but no results found")
                    return None
                    
            elif task_status == 'FAILED':
                error_message = result.get('output', {}).get('message', 'Unknown error')
                st.error(f"❌ Image generation failed: {error_message}")
                logger.error(f"Image generation failed: {error_message}")
                return None
                
            elif task_status in ['PENDING', 'RUNNING']:
                continue
        
        st.error("⏰ Image generation timed out")
        logger.error(f"Image generation timed out for task {task_id}")
        return None
        
    except requests.exceptions.HTTPError as http_err:
        error_msg = f"HTTP error occurred during image generation: {http_err}"
        if response_json and 'message' in response_json:
            error_msg += f" - API Message: {response_json['message']}"
        st.error(f"Failed to generate image: {error_msg}")
        logger.error(f"Failed to generate image: {error_msg} - Response: {response_json}")
        return None
    except requests.exceptions.RequestException as e:
        error_msg = str(e)
        st.error(f"Failed to generate image: {error_msg}")
        logger.error(f"Failed to generate image: {error_msg}")
        return None

# --- UI Sections ---

# Sidebar for Upload and Controls
with st.sidebar:
    st.title("🎬 Food Video Creator")
    st.markdown("Upload a food image and select a style to generate an appetizing video using Alibaba Cloud's **wanx-i2v** AI model.")

    uploaded_image_file = st.file_uploader(
        "1. Upload Food Image", 
        type=["png", "jpg", "jpeg"],
        help="Upload a clear image of the food item. PNG format is recommended."
    )

    st.markdown("---")
    st.subheader("2. Select Video Style")
    
    # Styles supported by wanx-i2v model as per documentation
    video_styles = [
        "<auto>", 
        "<cinematic>", 
        "<anime>", 
        "<oil painting>", 
        "<sketch>", 
        "<watercolor>", 
        "<3d cartoon>"
    ]
    selected_style = st.selectbox(
        "Choose a style:", 
        video_styles,
        index=0, # Default to <auto>
        help="Select a visual style for your video. '<auto>' lets the AI decide."
    )
    
    st.markdown("---")
    
    # API Configuration section
    with st.expander("⚙️ API Configuration", expanded=False):
        # Re-check API key status dynamically
        current_api_key = get_api_key()
        api_key_status = "✅ Configured" if current_api_key else "❌ Not configured"
        st.write(f"**API Key Status:** {api_key_status}")
        if not current_api_key:
            st.warning("Set DASHSCOPE_API_KEY environment variable or add to Streamlit secrets (`.streamlit/secrets.toml`).")
            st.code("DASHSCOPE_API_KEY = \"your-actual-api-key\"", language="toml")
        
        # R2 Configuration status
        st.markdown("---")
        r2_credentials = get_r2_credentials()
        r2_status = "✅ Configured" if r2_credentials else "❌ Not configured"
        st.write(f"**Cloudflare R2 Status:** {r2_status}")
        if not r2_credentials:
            st.warning("R2 storage is required for image uploads. Configure R2 credentials:")
            st.code("""# Add to .env or Streamlit secrets
R2_ACCESS_KEY_ID="your-r2-access-key"
R2_SECRET_ACCESS_KEY="your-r2-secret-key"
R2_ENDPOINT_URL="https://your-account-id.r2.cloudflarestorage.com"
R2_BUCKET_NAME="your-bucket-name"
R2_PUBLIC_URL_BASE="https://your-custom-domain.com"
            """, language="bash")


    # Option to use Mock Generator
    use_mock_generator = st.checkbox("🧪 Use Mock Video Generator (No API Call)", value=False, 
                                     help="If checked, simulates video generation without calling the API. Useful for testing UI.")


    generate_button = st.button(
        "Generate Appetizing Video", 
        type="primary", 
        use_container_width=True,
        disabled=not uploaded_image_file # Disable if no image is uploaded
    )

# Main Area for Image Preview and Video Output
st.header("✨ Your Generated Food Video ✨")

col1, col2 = st.columns(2, gap="medium")

# Initialize image and video_url in session state to persist them
if 'uploaded_image_pil' not in st.session_state:
    st.session_state.uploaded_image_pil = None
if 'generated_video_url' not in st.session_state:
    st.session_state.generated_video_url = None
if 'generated_mock_video_path' not in st.session_state:
    st.session_state.generated_mock_video_path = None


with col1:
    st.subheader("🖼️ Uploaded Image Preview")
    if uploaded_image_file:
        try:
            # Store the PIL image in session state if a new file is uploaded
            if st.session_state.get('last_uploaded_filename') != uploaded_image_file.name:
                st.session_state.uploaded_image_pil = Image.open(uploaded_image_file)
                st.session_state.last_uploaded_filename = uploaded_image_file.name
                # Clear previous video results when a new image is uploaded
                st.session_state.generated_video_url = None 
                st.session_state.generated_mock_video_path = None

            if st.session_state.uploaded_image_pil:
                st.image(st.session_state.uploaded_image_pil, caption="Your uploaded food image.", use_column_width=True)

        except Exception as e:
            st.error(f"Error displaying image: {e}")
            logger.error(f"Error processing/displaying uploaded image: {e}")
            st.session_state.uploaded_image_pil = None # Clear on error
    else:
        st.info("☝️ Please upload an image using the sidebar to see a preview.")

with col2:
    st.subheader("🎞️ Generated Video Output")
    
    if generate_button and uploaded_image_file and st.session_state.uploaded_image_pil:
        # Clear previous results before new generation
        st.session_state.generated_video_url = None
        st.session_state.generated_mock_video_path = None
        
        with st.spinner("🎬 Lights, Camera, Action! Generating your video... This can take several minutes."):
            try:
                current_image_pil = st.session_state.uploaded_image_pil
                
                if use_mock_generator:
                    logger.info("Using Mock Video Generator as selected by user.")
                    st.info("🧪 Using Mock Video Generator...")
                    mock_video_path = generate_mock_video(current_image_pil, selected_style)
                    if mock_video_path:
                        st.session_state.generated_mock_video_path = mock_video_path
                    else:
                        st.error("Mock video generation failed.")
                else:
                    logger.info("Using Alibaba WAN API for video generation.")
                    # Try to use the real WAN API for image-to-video
                    video_url_result = generate_video_with_wan(current_image_pil, selected_style)
                    if video_url_result:
                         st.session_state.generated_video_url = video_url_result
                    # Errors are handled within generate_video_with_wan

            except Exception as e:
                st.error(f"An unexpected error occurred during video generation: {str(e)}")
                logger.error(f"Unexpected error in main generation block: {str(e)}", exc_info=True)

    # Display logic based on session state
    if st.session_state.generated_video_url:
        st.success("🎉 Your appetizing food video is ready!")
        st.video(st.session_state.generated_video_url)
        
        st.markdown(f"""
        **Video Details:**
        - Style: `{selected_style}`
        - Duration: Approx. 5 seconds (as per API params)
        - Resolution: 1280x720 (as per API params)
        - Generated using Alibaba Cloud **wanx-i2v** AI
        
        **Note:** Video URL from Alibaba Cloud is typically valid for a limited time (e.g., 24 hours). Download if needed.
        """)
        logger.info(f"Video displayed to user. URL: {st.session_state.generated_video_url}")
    
    elif st.session_state.generated_mock_video_path:
        st.info("🧪 Mock video generated:")
        # For local mock files, st.video might not work directly if it's not a URL or common video format.
        # We'll just show a success message and the path.
        st.success(f"Mock video file created: `{st.session_state.generated_mock_video_path}`")
        st.markdown(f"This is a simulated video. To generate a real video, uncheck 'Use Mock Video Generator' and ensure your API key is set.")
        # If you create a real .mp4 for mock, you could use st.video(open(st.session_state.generated_mock_video_path, 'rb'))
    
    elif not uploaded_image_file and generate_button:
        st.warning("Please upload an image first before generating the video.")
    elif not generate_button and not st.session_state.generated_video_url and not st.session_state.generated_mock_video_path:
         st.info("Your generated video will appear here once you upload an image, select a style, and click 'Generate'.")


# --- Footer ---
st.markdown("---")
st.markdown(
    "🤖 Powered by **Alibaba Cloud WAN (万相) - wanx-i2v model**. "
    "Advanced AI for image-to-video generation."
)

# Setup instructions in expander
with st.expander("📋 Setup & Troubleshooting", expanded=False):
    st.markdown("""
    **To use this application with Alibaba Cloud API:**
    
    1.  **Get API Access:**
        * Visit [Alibaba Cloud Model Studio](https://www.alibabacloud.com/help/en/model-studio/getting-started/get-api-key) (DashScope).
        * Activate DashScope and obtain your `DASHSCOPE_API_KEY`.
        * Ensure the **wanx-i2v** model (or general video generation services) are enabled and you have sufficient quota/balance.

    2.  **Set API Key:**
        * **Recommended:** Create a file named `.streamlit/secrets.toml` in your project directory and add your key:
            ```toml
            DASHSCOPE_API_KEY = "sk-yourxxxxxxxxxxxxxxxxxxxxxxkey"
            ```
        * **Alternatively (less secure for sharing):** Set it as an environment variable:
            `export DASHSCOPE_API_KEY="sk-yourxxxxxxxxxxxxxxxxxxxxxxkey"`

    3.  **Install Dependencies:**
        If you have a `requirements.txt` file:
        ```bash
        pip install -r requirements.txt
        ```
        Ensure `streamlit`, `Pillow`, `requests`, `python-dotenv` are listed.

    4.  **Run the application:**
        ```bash
        streamlit run your_script_name.py
        ```
    
    **Troubleshooting:**
    * **API Key Errors:** Double-check your API key is correct and has the necessary permissions for DashScope video generation services.
    * **Task Fails (`FAILED` status):**
        * The image might be unsuitable (e.g., too complex, unsupported content, very low resolution). Try a different image.
        * The selected `style` might not work well with the image. Try `<auto>` or another style.
        * Check the error message provided by the API in the application or logs.
        * You might have hit API rate limits or account quota. Check your Alibaba Cloud console.
    * **Timeout:** Video generation can take time. If it times out, your connection might be slow, or the API queue might be long. Try again later.
    * **No Video URL:** If the task succeeds but no URL is returned, there might be an issue with the API's response format or an internal API error. Check the detailed JSON output in the app/logs.
    * **Check Logs:** The application logs to the console and displays some logs in the UI. These can provide clues.
    
    **Note:** Video generation via API can take 5-15 minutes depending on queue length and video complexity, and may incur costs on your Alibaba Cloud account.
    """)
