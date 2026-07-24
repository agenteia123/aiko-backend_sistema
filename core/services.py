"""Service manager for application lifecycle."""

import logging
from pathlib import Path

from config.settings import settings
from memory.manager import MemoryManager
from agent.core import get_agent


logger = logging.getLogger(__name__)


class ServiceManager:
    """Manage application services lifecycle."""
    
    _initialized = False
    
    @classmethod
    async def initialize(cls):
        """Initialize all services."""
        if cls._initialized:
            return
        
        logger.info("Initializing services...")
        
        # Create necessary directories
        cls._create_directories()
        
        # Initialize memory
        await MemoryManager.initialize()
        
        # Initialize agent
        await get_agent()
        
        cls._initialized = True
        logger.info("✅ All services initialized")
    
    @classmethod
    async def shutdown(cls):
        """Shutdown all services."""
        logger.info("Shutting down services...")
        
        # Shutdown memory
        await MemoryManager.shutdown()
        
        logger.info("✅ All services shut down")
    
    @staticmethod
    def _create_directories():
        """Create necessary directories."""
        dirs = [
            Path(settings.CHROMA_PERSIST_DIR),
            Path(settings.DB_PATH).parent,
            Path("./data"),
            Path("./logs"),
        ]
        
        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 Ensured directory: {dir_path}")
