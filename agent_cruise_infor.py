# create a new agent to get the cruise infor

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from db_tool import db_tool
from object.cruise_search_object import AgentState
from langgraph.graph import StateGraph, START, END
from promt.exact_infor_prompt import supervisor_cruise_infor_prompt, context_infor_cruise
from langchain_openai import ChatOpenAI
import logging
from typing import Literal, TypedDict
from langgraph.types import Command
from db_tool import cruise_infor_tool, get_cabin_tool
from utils import wrap_model
from object.cruise_search_object import CruiseSearchInfo
import asyncio
from langgraph.checkpoint.memory import MemorySaver

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # This will output to terminal
    ]
)
logger = logging.getLogger(__name__)

model=ChatOpenAI(model="gpt-4o-mini", temperature=0)

members = ["general_cruise_infor", "cabin_infor", "add_cart"]
options = members + ["FINISH"]
class Router(TypedDict):
    next: Literal[*options]


async def cruise_infor_supervisor_node(state: AgentState, config: dict) -> AgentState:
    logger.info(f"Cruise Infor Supervisor node called with state: {state}")
    wrapped_model = wrap_model(model, supervisor_cruise_infor_prompt(state.get("description", None)), Router)
    response=await wrapped_model.ainvoke(state, config)
    logger.info(f"Cruise Infor Supervisor node response: {response}")
    goto = response["next"]   
    if goto == "FINISH":
        return Command(goto=END)
    elif goto == "add_cart":
        return Command(goto=END, update={"messages": [HumanMessage(content="I've added the cabin to the cart", name="add_cart")],
                                        "cruises": [],
                                        "current_cruise": state.get("current_cruise", {}),
                                        "chat_history": state.get("chat_history", ""),
                                        "currency": state.get("currency", "USD"),
                                        "cruise_search_info": state.get("cruise_search_info", CruiseSearchInfo()),
                                        "action": "show_cabin",
                                        "list_cabin": [],
                                        "description": state.get("description", "")})
    else:
        return Command(goto=goto, update={"next": goto})

async def general_cruise_infor_node(state: AgentState, config: dict) -> AgentState:
    logger.info(f"General Cruise Infor node called with state: {state}")
    cruise_id = state["current_cruise"]["id"]
    cruise_info = await cruise_infor_tool.ainvoke(cruise_id, currency = state["currency"])
    
    wrapped_model = wrap_model(model, context_infor_cruise(cruise_info))
    response = await wrapped_model.ainvoke(state, config)
    logger.info(f"General Cruise Infor node response: {response}")
    
    return {"messages": [HumanMessage(content=response.content, name="general_cruise_infor")],
            "cruises": [cruise_info],
            "current_cruise": state.get("current_cruise", {}),
            "chat_history": state.get("chat_history", ""),
            "currency": state.get("currency", "USD"),
            "cruise_search_info": state.get("cruise_search_info", CruiseSearchInfo()),
            "action": "",
            "list_cabin": [],
            "description": None}
async def cabin_infor_node(state: AgentState, config: dict) -> AgentState:
    logger.info(f"Cabin Infor node called with state: {state}")
    list_cabin = await get_cabin_tool.ainvoke(state["current_cruise"]["id"], currency = state["currency"])
    return {"messages": [HumanMessage(content="Carbin infor", name="carbin_infor")],
            "cruises": [],
            "current_cruise": state.get("current_cruise", {}),
            "chat_history": state.get("chat_history", ""),
            "currency": state.get("currency", "USD"),
            "cruise_search_info": state.get("cruise_search_info", CruiseSearchInfo()),
            "action": "show_cabin",
            "list_cabin": list_cabin,
            "description": None}   
agent=StateGraph(AgentState)
agent.add_edge(START, "cruise_infor_supervisor")
agent.add_node("cruise_infor_supervisor", cruise_infor_supervisor_node)
agent.add_node("general_cruise_infor", general_cruise_infor_node)
agent.add_node("cabin_infor", cabin_infor_node)


agent.add_edge("general_cruise_infor", END)
agent.add_edge("cabin_infor", END)
chatbot_cruise_infor =agent.compile(checkpointer=MemorySaver())

if __name__ == "__main__":
    configurable = {
            "thread_id": 1
        }
    config = {"configurable": configurable}
    # kwargs = {
    #             "input": {"messages": [HumanMessage(content="Get the price of this cruise")],
    #                       "current_cruise": {"id": "6787671e9eced029e8747030"},
    #                       "currency": "USD"
    #                       },
                          
    #             "config": config,
    #         }
    # kwargs = {
    #         "input": {"messages": [HumanMessage(content="Show me the list cabins of cruise")],
    #                     "current_cruise": {"id": "6787671e9eced029e8747030"},
    #                     "currency": "USD"
    #                     },
                        
    #         "config": config,
    #     }
    kwargs = {
            "input": {"messages": [HumanMessage(content="Add to the cart")],
                        "current_cruise": {"id": "6787671e9eced029e8747030"},
                        "currency": "USD"
                        },
                        
            "config": config,
        }


    response = asyncio.run(chatbot_cruise_infor.ainvoke(**kwargs))
    print(response)
