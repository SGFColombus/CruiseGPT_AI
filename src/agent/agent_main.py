import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from dotenv import load_dotenv

load_dotenv()


import logging
from typing import Literal
from uuid import uuid4
from pydantic import BaseModel, Field
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage


from agent.objects.objects import AgentState
from agent.agent_members.cruise_agent import build_cruise_agent

from agent.prompts.agent_main_prompt import agent_main_routing_prompt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],  # This will output to terminal
)
logger = logging.getLogger(__name__)


class Route(BaseModel):
    step: Literal["cruise_node", "general_node"] = Field(
        None, description=" The next step in the rounting process"
    )


llm = ChatOpenAI(model="gpt-4o-mini")
router = llm.with_structured_output(Route)


def language_detector(state: AgentState, config: dict):
    prompt = "You are a language detector. You are responsible for detecting the language of the user's query. Respond with language of the user's query. Do not add any additional information."
    language = llm.invoke([SystemMessage(content=prompt), state.messages[-1]])
    return {"language": language.content}


def supervisor_node(state: AgentState, config: dict):
    logger.info(f"Supervisor node called with state: {state}")

    routing_agent = router.invoke(
        [SystemMessage(content=agent_main_routing_prompt)] + state.messages
    )
    return {"agent_routing": routing_agent.step}


def routing(state: AgentState, config: dict):
    logger.info(f"Routing node called with state: {state}")
    routing_agent = state.agent_routing
    if routing_agent == "cruise_node":
        return "cruise_node"
    return "general_node"


def general_node(state: AgentState, config: dict) -> AgentState:
    logger.info(f"General infor node called with state: {state}")
    prompt = "You are a general information agent. You are responsible for providing general information to the user. However, it's under development, so respond with suggestion that clarify query related to cruise agent.\n\nIMPORTANT: Response must be in user's language."

    return {
        "messages": [llm.invoke([SystemMessage(content=prompt)] + state.messages)],
    }


def language_translator(state: AgentState, config: dict):
    prompt = f"You are a language translator, working in cruise industry. You are responsible for translating the user's query to the language of the user. Language style should be joyfull, but concise. The language of the user is {state.language}."
    language_translator = llm.invoke(
        [SystemMessage(content=prompt), state.messages[-1]]
    )
    return {"messages": [language_translator]}


def create_agent():
    agent = StateGraph(AgentState)

    agent.add_node("language_node", language_detector)
    agent.add_node("supervisor", supervisor_node)
    agent.add_node("cruise_node", build_cruise_agent())
    agent.add_node("general_node", general_node)
    agent.add_node("language_translator", language_translator)

    agent.add_edge(START, "language_node")
    agent.add_edge("language_node", "supervisor")
    agent.add_conditional_edges(
        "supervisor",
        routing,
        {
            "cruise_node": "cruise_node",
            "general_node": "general_node",
        },
    )
    agent.add_edge("cruise_node", "language_translator")
    agent.add_edge("general_node", "language_translator")
    agent.add_edge("language_translator", END)

    return agent.compile(checkpointer=MemorySaver())


agent_main = create_agent()

if __name__ == "__main__":

    configurable = {"thread_id": 1}
    run_id = uuid4()
    config = {"configurable": configurable}

    messages = agent_main.invoke(
        input={
            "messages": [HumanMessage("Do you have any cruises to Lisbon?")],
            "current_cruise": {"id": "6787671e9eced029e8747030"},
        },
        config=config,
    )
    for m in messages["messages"]:
        m.pretty_print()
