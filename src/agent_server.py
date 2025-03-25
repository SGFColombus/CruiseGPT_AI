import os
import sys

sys.path.insert(0, "..")
import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import openai

# import HumanMessage and RunnableConfig
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from langchain_core.runnables import RunnableConfig


from agent.agent_main import agent_main

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Validate OpenAI API key
api_key = os.getenv("OPENAI_API_KEY")
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
    currentCruiseId: Optional[str] = None
    country: Optional[str] = "US"
    currency: Optional[str] = "USD"
    description: Optional[str] = None
    userId: Optional[str] = None


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

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5000", "https://localhost:5000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def chat_response(user_input: dict, config: dict, agent):
    snapshot = agent.get_state(config)
    if snapshot.next:
        value_from_human = user_input["messages"][-1].content
        messages = agent.invoke(Command(resume=value_from_human), config=config)
    else:
        messages = agent.invoke(input=user_input, config=config)

    snapshot = agent.get_state(config)
    if snapshot.next:
        ai_message = snapshot.tasks[0].interrupts[0].value
        return ai_message, snapshot.tasks[0].state
    return messages["messages"][-1].content, snapshot.values


@app.get("/health")
async def health_check():
    """Health check endpoint to verify server status"""
    try:
        # Verify OpenAI connectivity
        await openai.chat.completions.create(
            model="gpt-4", messages=[{"role": "user", "content": "test"}], max_tokens=5
        )
        return {"status": "healthy", "openai": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=503, detail="Service unhealthy: OpenAI connection failed"
        )


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Chat endpoint that processes user messages and returns AI responses"""
    try:
        logger.info(f"Processing chat request: {request}")
        session_id = request.sessionId
        session_id = session_id.replace('"', "")
        user_id = request.userId
        # run_id = session_id
        configurable = {"thread_id": session_id, "user_id": user_id}
        kwargs = {
            "user_input": {
                "messages": [HumanMessage(content=request.message)],
                "cruises": [],
                # "chat_history": chat_history,
                "currency": request.currency,
                "country": request.country,
                "current_cruise_id": request.currentCruiseId,
                "current_cabin": request.description,
                "action": "",
            },
            "config": RunnableConfig(
                configurable=configurable,
                # run_id=run_id,
            ),
        }
        ai_message, state = chat_response(**kwargs, agent=agent_main)

        output_dict = {
            "message": ai_message,
            "cruises": state.get("list_cruises", []),
            "sessionId": str(session_id),
            "currency": request.currency,
            "country": request.country,
            "currentCruiseId": state.get("current_cruise_id", ""),
            "description": state.get("current_cabin", ""),
        }
        if "action" in state.keys():
            output_dict["action"] = state["action"]
        if "list_cabins" in state.keys():
            output_dict["cabins"] = state["list_cabins"]
        logger.info(f"Output dictionary: {output_dict}")
        return output_dict

    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise e
        raise HTTPException(status_code=500, detail="Failed to process chat request")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "5001"))
    logger.info(f"Starting FastAPI server on port {port}")
    uvicorn.run(
        "agent_server:app", host="0.0.0.0", port=port, log_level="info", reload=True
    )
