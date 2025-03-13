import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import openai
from scripts.origin.chat_service import ChatService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Validate OpenAI API key
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    logger.error("OPENAI_API_KEY environment variable is not set")
    sys.exit(1)

try:
    # Initialize OpenAI client
    openai.api_key = api_key
    logger.info("OpenAI client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {e}")
    sys.exit(1)

# Request/Response models
class ChatRequest(BaseModel):
    message: str
    sessionId: Optional[str] = None

class ChatResponse(BaseModel):
    message: str
    cruise: Optional[Dict[str, Any]] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up FastAPI server...")
    yield
    # Shutdown
    logger.info("Shutting down FastAPI server...")

app = FastAPI(lifespan=lifespan)
chat_service = ChatService()
# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5000", "https://localhost:5000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Health check endpoint to verify server status"""
    try:
        # Verify OpenAI connectivity
        await openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=5
        )
        return {
            "status": "healthy",
            "openai": "connected"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="Service unhealthy: OpenAI connection failed"
        )

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Chat endpoint that processes user messages and returns AI responses"""
    try:
        logger.info(f"Processing chat request: {request.message}")
        
#         response = await openai.chat.completions.create(
#             model="gpt-3.5-turbo",
#             messages=[
#                 {
#                     "role": "system",
#                     "content": """You are a knowledgeable cruise booking assistant for a luxury cruise platform. Help users find their perfect cruise vacation by understanding their preferences and providing personalized recommendations.

# When users ask questions or express interest in cruises, analyze their preferences for:
# - Destination preferences (Caribbean, Mediterranean, Alaska, etc.)
# - Duration (number of nights)
# - Budget considerations
# - Special interests (family activities, luxury, adventure, etc.)
# - Timing/season preferences

# Always respond in JSON format with:
# {
#   "message": "Your friendly and informative response here",
#   "cruise": {
#     "id": "unique-id",
#     "name": "Descriptive cruise name",
#     "itinerary": "Detailed route with ports of call",
#     "duration": 7,
#     "price": 899,
#     "image": "https://images.unsplash.com/photo-1491251880772-1fe1c8b6d5f6",
#     "departureDate": "2024-06-15",
#     "returnDate": "2024-06-22",
#     "cabinTypes": [
#       {"type": "Interior", "price": 899, "available": 50},
#       {"type": "Ocean View", "price": 1099, "available": 30},
#       {"type": "Balcony", "price": 1399, "available": 20}
#     ]
#   }
# }

# The cruise object should only be included when making a specific recommendation."""
#                 },
#                 {
#                     "role": "user",
#                     "content": request.message
#                 }
#             ],
#             response_format={"type": "json_object"}
#         )
        
#         result = json.loads(response.choices[0].message.content)
#         logger.info(f"Generated response: {result}")
        result = await chat_service.chat_with_context(request.message, 1)
        logger.info(f"Generated response: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to process chat request"
        )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('PORT', '5001'))
    logger.info(f"Starting FastAPI server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
