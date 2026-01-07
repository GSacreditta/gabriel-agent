import logging
import asyncio
from pyngrok import ngrok
from ..core.config import get_settings

logger = logging.getLogger(__name__)

class NgrokService:
    """Service for managing Ngrok tunnel."""
    
    def __init__(self):
        """Initialize the Ngrok service."""
        self.settings = get_settings()
        self.tunnel = None
        self.public_url = None
        
    async def start(self):
        """Start the Ngrok tunnel."""
        try:
            logger.info("Starting Ngrok tunnel...")
            
            # Set auth token if provided
            if self.settings.NGROK_AUTH_TOKEN:
                ngrok.set_auth_token(self.settings.NGROK_AUTH_TOKEN)
            
            # Start tunnel
            self.tunnel = ngrok.connect(
                addr=8000,  # Default FastAPI port
                proto="http",
                bind_tls=True,
                domain=self.settings.NGROK_DOMAIN if self.settings.NGROK_DOMAIN else None
            )
            
            self.public_url = self.tunnel.public_url
            logger.info(f"Ngrok tunnel started at: {self.public_url}")
            
            return {
                "success": True,
                "public_url": self.public_url
            }
            
        except Exception as e:
            logger.error(f"Error starting Ngrok tunnel: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def stop(self):
        """Stop the Ngrok tunnel."""
        try:
            logger.info("Stopping Ngrok tunnel...")
            
            if self.tunnel:
                ngrok.disconnect(self.tunnel.public_url)
                self.tunnel = None
                self.public_url = None
                logger.info("Ngrok tunnel stopped")
            
            return {
                "success": True,
                "message": "Ngrok tunnel stopped successfully"
            }
            
        except Exception as e:
            logger.error(f"Error stopping Ngrok tunnel: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def cleanup(self):
        """Cleanup Ngrok resources."""
        try:
            await self.stop()
            ngrok.kill()  # Kill the Ngrok process
            logger.info("Ngrok resources cleaned up")
        except Exception as e:
            logger.warning(f"Error during Ngrok cleanup: {str(e)}") 