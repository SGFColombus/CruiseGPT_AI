from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import openai
import os
import uvicorn
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Enable CORS with specific origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5000", "https://localhost:5000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure OpenAI
openai.api_key = os.environ.get('OPENAI_API_KEY')
if not openai.api_key:
    logger.error("OPENAI_API_KEY environment variable is not set")
    raise ValueError("OPENAI_API_KEY environment variable is not set")

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    message: str
    cruise: Optional[Dict[str, Any]] = None

@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        logger.info(f"Processing chat request with message: {request.message}")
        
        response = await openai.chat.completions.create(
            model="gpt-3.5-turbo",  # Temporarily using gpt-4 for testing
            messages=[
                {
                    "role": "system",
                    "content": """You are a knowledgeable cruise booking assistant for a luxury cruise platform. Help users find their perfect cruise vacation by understanding their preferences and providing personalized recommendations.

When users ask questions or express interest in cruises, analyze their preferences for:
- Destination preferences (Caribbean, Mediterranean, Alaska, etc.)
- Duration (number of nights)
- Budget considerations
- Special interests (family activities, luxury, adventure, etc.)
- Timing/season preferences

Always respond in JSON format with:
{
  "message": "Your friendly and informative response here",
  "cruise": {
    "id": "unique-id",
    "name": "Descriptive cruise name",
    "itinerary": "Detailed route with ports of call",
    "duration": 7,
    "price": 899,
    "image": "https://images.unsplash.com/photo-1491251880772-1fe1c8b6d5f6",
    "departureDate": "2024-06-15",
    "returnDate": "2024-06-22",
    "cabinTypes": [
      {"type": "Interior", "price": 899, "available": 50},
      {"type": "Ocean View", "price": 1099, "available": 30},
      {"type": "Balcony", "price": 1399, "available": 20}
    ]
  }
}

The cruise object should only be included when making a specific recommendation. Focus on understanding the user's needs and providing relevant suggestions."""
                },
                {
                    "role": "user",
                    "content": request.message
                }
            ],
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        print(f"OpenAI response: {result}")  # Debug log
        return result

    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="I apologize, but I'm having trouble processing your request right now. Please try again."
        )

if __name__ == "__main__":
    print("Starting FastAPI server on port 5001...")
    uvicorn.run(app, host="0.0.0.0", port=5001)
