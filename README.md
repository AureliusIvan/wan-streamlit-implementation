# WAN Video Generator

AI-Powered Video Creation using Alibaba Cloud WAN (万相) model with Streamlit interface.

## Features

- **Direct Image-to-Video**: Upload an image and generate a video directly
- **Text-to-Image-to-Video**: Describe an image and generate a video from it
- **Image Enhancement**: Extract description, enhance image, then generate video
- Multiple video styles supported
- Cloudflare R2 storage integration for better performance

## Quick Start with uv

This project uses [uv](https://github.com/astral-sh/uv) for fast Python package management.

### Prerequisites

1. **Install uv** (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Get API Access**:
   - Visit [Alibaba Cloud Model Studio](https://www.alibabacloud.com/help/en/model-studio/getting-started/get-api-key)
   - Activate DashScope and obtain your `DASHSCOPE_API_KEY`
   - Ensure video generation services are enabled with sufficient quota

### Setup

1. **Clone and setup**:
   ```bash
   git clone <repository-url>
   cd wan-video-generator
   make setup
   ```

2. **Configure API Key**:
   ```bash
   cp .env.example .env.local
   # Edit .env.local and add your DASHSCOPE_API_KEY
   ```

3. **Run the application**:
   ```bash
   make run
   ```

The application will be available at http://localhost:8501

## Available Commands

Use `make help` to see all available commands:

### Setup & Installation
- `make setup` - Create virtual environment and install dependencies with uv
- `make install` - Install production dependencies
- `make dev-install` - Install development dependencies
- `make sync` - Sync dependencies from pyproject.toml
- `make lock` - Update uv.lock file

### Development
- `make run` - Run the Streamlit application
- `make dev` - Run in development mode with auto-reload
- `make check` - Run all code quality checks
- `make lint` - Run linting checks
- `make format` - Format code with black
- `make test` - Run tests

### Package Management
- `make add` - Add a new package
- `make add-dev` - Add a development package
- `make remove` - Remove a package
- `make tree` - Show dependency tree

## Environment Variables

Create a `.env.local` file with the following variables:

```env
# Required
DASHSCOPE_API_KEY=your_dashscope_api_key_here

# Optional - Cloudflare R2 Storage (for better performance)
R2_ACCOUNT_ID=your_r2_account_id
R2_ACCESS_KEY_ID=your_r2_access_key
R2_SECRET_ACCESS_KEY=your_r2_secret_key
R2_BUCKET_NAME=your_bucket_name
```

## Project Structure

```
wan-video-generator/
├── main.py                 # Main Streamlit application
├── pyproject.toml         # Project configuration and dependencies
├── .python-version        # Python version specification
├── Makefile              # Build and development commands
├── config/               # Configuration modules
│   ├── settings.py       # Settings and environment handling
│   └── logging_config.py # Logging configuration
├── services/             # External service integrations
│   ├── wan_api.py        # Alibaba Cloud WAN API client
│   ├── qwen_service.py   # Qwen model service
│   └── r2_storage.py     # Cloudflare R2 storage
├── ui/                   # UI components
│   └── components.py     # Streamlit UI components
├── utils/                # Utility functions
│   └── helpers.py        # Helper functions
└── constants/            # Application constants
    └── api_constants.py  # API-related constants
```

## Migration from pip to uv

This project has been migrated from traditional pip/venv to uv for faster dependency management. Key changes:

- **Dependencies**: Moved from `requirements.txt` to `pyproject.toml`
- **Virtual Environment**: Uses `.venv/` instead of `venv/`
- **Commands**: All `pip` commands replaced with `uv` equivalents
- **Lock File**: `uv.lock` for reproducible builds
- **Performance**: 10-100x faster package installation and resolution

### For Existing Users

If you have an existing installation:

1. Remove old virtual environment: `rm -rf venv/`
2. Run setup: `make setup`
3. Your project will now use uv for package management

## Development

### Code Quality

The project includes automated code quality tools:

```bash
make format    # Format code with black
make lint      # Check code with flake8
make check     # Run all quality checks
```

### Testing

```bash
make test      # Run pytest
```

### Adding Dependencies

```bash
# Add production dependency
make add
# Enter package name when prompted

# Add development dependency
make add-dev
# Enter package name when prompted
```

## Troubleshooting

### API Issues
- Check API key permissions and quota in Alibaba Cloud console
- Try different images or styles if generation fails
- Video generation can take 5-15 minutes depending on queue
- Monitor logs for detailed error information

### uv Issues
- Install uv: `make install-uv`
- Check uv status: `make status`
- Sync dependencies: `make sync`

## License

[Add your license here]

## Contributing

[Add contributing guidelines here]
