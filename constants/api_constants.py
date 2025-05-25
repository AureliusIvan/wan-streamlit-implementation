"""
API Constants and Configuration Values
"""

# API Base URLs
WAN_API_BASE_URL = "https://dashscope-intl.aliyuncs.com/api/v1"

# API Endpoints
WAN_VIDEO_ENDPOINT = f"{WAN_API_BASE_URL}/services/aigc/video-generation/video-synthesis"
WAN_TEXT_TO_IMAGE_ENDPOINT = f"{WAN_API_BASE_URL}/services/aigc/text2image/image-synthesis"
QWEN_VL_ENDPOINT = f"{WAN_API_BASE_URL}/services/aigc/multimodal-generation/generation"
WAN_TASK_ENDPOINT = f"{WAN_API_BASE_URL}/tasks"

# Model Names
WAN_I2V_MODEL = "wan2.1-i2v-turbo"
WAN_T2I_MODEL = "wan2.1-t2i-turbo"
QWEN_VL_MODEL = "qwen-vl-plus-latest"

# Video Styles
VIDEO_STYLES = [
    "<auto>", 
    "<cinematic>", 
    "<anime>", 
    "<oil painting>", 
    "<sketch>", 
    "<watercolor>", 
    "<3d cartoon>"
]

# API Configuration
MAX_RETRIES = 3
VIDEO_POLL_INTERVAL = 5
IMAGE_POLL_INTERVAL = 3
MAX_VIDEO_ATTEMPTS = 180  # 180 * 5s = 15 minutes
MAX_IMAGE_ATTEMPTS = 60   # 60 * 3s = 3 minutes

# Image Processing
MAX_IMAGE_SIZE = 1024
IMAGE_QUALITY = 85

# File Upload
SUPPORTED_IMAGE_TYPES = ["png", "jpg", "jpeg"]

# R2 Storage
R2_IMAGE_PREFIX = "wan-images"
R2_CACHE_CONTROL = "max-age=86400"  # 24 hours