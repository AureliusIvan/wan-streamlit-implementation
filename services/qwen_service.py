"""
Qwen VL Service for Image Description Extraction
"""

import json
import logging
import requests
import streamlit as st

from services.r2_storage import upload_image_to_r2
from constants.api_constants import QWEN_VL_ENDPOINT, QWEN_VL_MODEL

logger = logging.getLogger("wan-video")


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
        "model": QWEN_VL_MODEL,
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