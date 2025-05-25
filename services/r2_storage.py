"""
Cloudflare R2 Storage Service
"""

import boto3
import uuid
import datetime
import logging
from io import BytesIO
from PIL import Image
from botocore.exceptions import ClientError, NoCredentialsError
import streamlit as st

from config.settings import get_r2_credentials
from constants.api_constants import R2_IMAGE_PREFIX, R2_CACHE_CONTROL, MAX_IMAGE_SIZE, IMAGE_QUALITY

logger = logging.getLogger("wan-video")


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
        if max(image_pil.size) > MAX_IMAGE_SIZE:
            image_pil.thumbnail((MAX_IMAGE_SIZE, MAX_IMAGE_SIZE), Image.Resampling.LANCZOS)
            logger.info(f"[INTERNAL] Image resized to {image_pil.size} for R2 upload.")
        
        # Convert to bytes
        buffered = BytesIO()
        image_pil.save(buffered, format="JPEG", quality=IMAGE_QUALITY)
        image_bytes = buffered.getvalue()
        
        # Generate unique filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"{R2_IMAGE_PREFIX}/{timestamp}_{unique_id}.jpg"
        
        # Upload to R2
        client.put_object(
            Bucket=credentials['bucket_name'],
            Key=filename,
            Body=image_bytes,
            ContentType='image/jpeg',
            CacheControl=R2_CACHE_CONTROL
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