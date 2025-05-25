"""
WAN API Service for Video Generation and Text-to-Image
"""

import json
import time
import logging
import requests
from io import BytesIO
from PIL import Image
import streamlit as st

from config.settings import get_api_key
from services.r2_storage import upload_image_to_r2
from constants.api_constants import (
    WAN_VIDEO_ENDPOINT, WAN_TEXT_TO_IMAGE_ENDPOINT, WAN_TASK_ENDPOINT,
    WAN_I2V_MODEL, WAN_T2I_MODEL, MAX_RETRIES, MAX_VIDEO_ATTEMPTS, 
    MAX_IMAGE_ATTEMPTS, VIDEO_POLL_INTERVAL, IMAGE_POLL_INTERVAL
)

logger = logging.getLogger("wan-video")


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
    
    payload = {
        "model": WAN_I2V_MODEL,
        "input": {
            "prompt": "An appetizing food",
            "img_url": image_url
        },
        "parameters": {
            "resolution": "720P",
            "prompt_extend": True
        }
    }
    
    # Add style parameter if not auto
    if selected_style != "<auto>":
        payload["parameters"]["style"] = selected_style

    logger.info(f"Creating image-to-video task with model: {payload['model']}, style: {selected_style}")
    logger.debug(f"[INTERNAL] Payload: {json.dumps(payload, indent=2)}")
    
    # Add retry logic for transient errors
    for attempt in range(MAX_RETRIES):
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
                logger.warning(f"InternalError on attempt {attempt + 1}/{MAX_RETRIES}: {response_json.get('output', {}).get('message', 'Unknown')}")
                
                if attempt == MAX_RETRIES - 1:  # Last attempt
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
            if attempt == MAX_RETRIES - 1:
                error_msg = str(e)
                st.error(f"API request failed after {MAX_RETRIES} attempts: {error_msg}")
                logger.error(f"API request failed: {error_msg}")
                return None
            else:
                logger.warning(f"Request exception on attempt {attempt + 1}, retrying: {str(e)}")
                time.sleep(2)
                continue
    
    return None


def generate_image_from_text_with_wan(description, api_key):
    """Generate image from text description using WAN text-to-image model"""
    st.info("🎨 Generating new image from description...")
    
    headers = {
        'X-DashScope-Async': 'enable',
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        "model": WAN_T2I_MODEL,
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
        
        for attempt in range(MAX_IMAGE_ATTEMPTS):
            time.sleep(IMAGE_POLL_INTERVAL)
            
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


def poll_video_task(task_id, api_key):
    """Poll for video generation results"""
    st.info("🔄 Processing video... This may take 5-10 minutes depending on queue.")
    logger.info(f"Polling for video task status (Task ID: {task_id})...")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for attempt in range(MAX_VIDEO_ATTEMPTS):
        progress = min((attempt + 1) / MAX_VIDEO_ATTEMPTS, 0.95)
        progress_bar.progress(progress)
        
        status_text.text(f"Checking video status... (Attempt {attempt + 1}/{MAX_VIDEO_ATTEMPTS})")
        logger.info(f"Polling attempt {attempt + 1}/{MAX_VIDEO_ATTEMPTS} for video task {task_id}")
        
        time.sleep(VIDEO_POLL_INTERVAL)
        
        result = check_task_status(task_id, api_key)
        if not result:
            logger.warning(f"Attempt {attempt + 1}: Failed to get task status or received null result. Retrying...")
            if attempt == MAX_VIDEO_ATTEMPTS - 1:
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
    logger.error(f"Video generation for task {task_id} timed out after {MAX_VIDEO_ATTEMPTS} attempts.")
    return None