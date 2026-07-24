"""Image analysis tool using vision models."""

import logging
import base64
from pathlib import Path

from langchain_core.tools import Tool

logger = logging.getLogger(__name__)


class ImageAnalysisTool:
    """Tool for analyzing images."""
    
    def __init__(self):
        """Initialize image analysis tool."""
        self.llm_with_vision = None
        self._init_vision_model()
    
    def _init_vision_model(self):
        """Initialize vision model."""
        try:
            from langchain_openai import ChatOpenAI
            from config.settings import settings
            
            if settings.OPENAI_API_KEY:
                self.llm_with_vision = ChatOpenAI(
                    api_key=settings.OPENAI_API_KEY,
                    model="gpt-4-vision-preview",
                )
                logger.info("✅ Vision model initialized (OpenAI)")
            else:
                logger.warning("Vision model not available (no OpenAI API key)")
        except Exception as e:
            logger.warning(f"Vision model initialization failed: {e}")
    
    def get_tool(self) -> Tool:
        """Get the image analysis tool."""
        return Tool(
            name="analyze_image",
            description="Analyze an image and describe its contents. Provide the file path to the image.",
            func=self.analyze_image,
        )
    
    def analyze_image(self, image_path: str, query: str = "Describe this image") -> str:
        """Analyze an image."""
        try:
            if not Path(image_path).exists():
                return f"Image not found: {image_path}"
            
            if not self.llm_with_vision:
                return "Vision model not available"
            
            # Read and encode image
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")
            
            # Get file extension to determine media type
            ext = Path(image_path).suffix.lower()
            media_type_map = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp",
            }
            media_type = media_type_map.get(ext, "image/jpeg")
            
            # Analyze image
            from langchain_core.messages import HumanMessage
            
            message = HumanMessage(
                content=[
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{image_data}",
                        },
                    },
                    {
                        "type": "text",
                        "text": query,
                    },
                ],
            )
            
            response = self.llm_with_vision.invoke([message])
            return str(response.content)
        except Exception as e:
            logger.error(f"Image analysis error: {e}")
            return f"Error analyzing image: {str(e)}"
