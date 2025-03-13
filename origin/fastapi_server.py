import logging
import os
import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import openai
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        logger.info(f"Processing chat request: {request.message}")

        if not os.getenv('OPENAI_API_KEY'):
            return JSONResponse(
                status_code=500,
                content={"message": "OpenAI API key not configured"}
            )

        client = openai.OpenAI()
        response = await client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a knowledgeable cruise booking assistant."},
                {"role": "user", "content": request.message}
            ],
            response_format={"type": "json_object"}
        )

        return JSONResponse(content=response.choices[0].message.content)

    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"message": "Service temporarily unavailable"}
        )

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    port = 5001
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")