from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from langgraph.graph import MessagesState, END
from promt.exact_infor_prompt import extract_infor_promt
from db_tool import db_query_tool, cruise_infor_tool
from typing import Literal, TypedDict
from langgraph.graph import END, START
from promt.supervior_prompt import get_supervior_prompt
from langgraph.types import Command
from langchain_core.tools import BaseTool
from uuid import uuid4
import logging
from promt.exact_infor_prompt import context_infor_cruise
import json
from object.cruise_search_object import CruiseSearchInfo, AgentState
from utils import wrap_model
from agent_cruise_infor import chatbot_cruise_infor
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # This will output to terminal
    ]
)
logger = logging.getLogger(__name__)
     

members = ["general_infor", "cruise_search", "cruise_infor", "clear_context"]
options = members + ["FINISH"]
class Router(TypedDict):
    next: Literal[*options]

model = ChatOpenAI(model="gpt-4o-mini")

async def supervisor_node(state: AgentState, config: dict) -> Command[Literal[*members,END]]:
    logger.info(f"Supervisor node called with state: {state}")
    if state["current_cruise"] is not None:
        current_cruise = state["current_cruise"]
    wrapped_model = wrap_model(model, get_supervior_prompt(members, current_cruise), Router)
    response = await wrapped_model.ainvoke(state, config)
    logger.info(f"Supervisor node response: {response}")
    goto = response["next"]   
    if goto == "FINISH":
        return Command(goto=END)
    return Command(goto=goto, update={"next": goto})
def enrich_cruise_search_info(current_info: CruiseSearchInfo, update_info: CruiseSearchInfo) -> CruiseSearchInfo:
    logger.info(f"===================================")
    logger.info(f"Current info: {current_info}")
    logger.info(f"Update info: {update_info}")
    for field, value in update_info.dict(exclude_unset=True).items():
        if value is not None:
            setattr(current_info, field, value)
    logger.info(f"Updated info: {current_info}")
    logger.info(f"===================================")
    return current_info
async def cruise_search_node(state: AgentState, config: dict) -> AgentState:
    logger.info(f"Cruise search node called with state: {state}")
    model_with_structured_output = model.with_structured_output(CruiseSearchInfo)
    wrapped_model = wrap_model(model=model_with_structured_output,
                               system_prompt=extract_infor_promt(state.get("cruise_search_info", "")))
    response = await wrapped_model.ainvoke(state, config)
    cruise_search_info = enrich_cruise_search_info(state.get("cruise_search_info", CruiseSearchInfo()), response)
    logger.info(f"Cruise search node response: {response}")
    logger.info(f"Cruise search info: {cruise_search_info}")
    # We return a list, because this will get added to the existing list
    return {"messages": [HumanMessage(content=response.message, name="cruise_search")],
            "cruises": state.get("cruises", []),
            "current_cruise": state.get("current_cruise", {}),
            "chat_history": state.get("chat_history", ""),
            "currency": state.get("currency", "USD"),
            "cruise_search_info": cruise_search_info,
            "action": "",
            "list_cabin": []}

async def cruise_infor_node(state: AgentState, config: dict) -> AgentState:
    logger.info(f"Cruise infor node called with state: {state}")
    # cruise_id = state["current_cruise"]["id"]
    # cruise_infor_agent = await cruise_infor_tool.ainvoke(cruise_id, currency = state["currency"])
    # logger.info(f"Cruise infor node response: {str(cruise_infor_agent)}")
    # wrapped_model = wrap_model(model=model, system_prompt=context_infor_cruise(cruise_infor_agent))
    # response = await wrapped_model.ainvoke(state, config)
    # logger.info(f"Cruise infor node response: {response}")
    response = await chatbot_cruise_infor.ainvoke(state, config)
    return {"messages": [HumanMessage(content=response.get("messages", [""])[0].content, name="cruise_infor")],
            "cruises": response.get("cruises", []),
            "current_cruise": state.get("current_cruise", {}),
            "chat_history": state.get("chat_history", ""),
            "currency": state.get("currency", "USD"),
            "cruise_search_info": state.get("cruise_search_info", CruiseSearchInfo()),
            "action": response.get("action", ""),
            "list_cabin": response.get("list_cabin", [])}

# async def add_cart_node(state: AgentState, config: dict) -> AgentState:
#     logger.info(f"Add cart node called with state: {state}")
#     cruise_id = state["current_cruise"]["id"]
#     cruise_infor_agent = await cruise_infor_tool.ainvoke(cruise_id, currency = state["currency"])
#     return {"messages": [HumanMessage(content="Yes, I've add this cruise into cart", name="add_cart")],
#             "cruises": [cruise_infor_agent],
#             "current_cruise": state.get("current_cruise", {}),
#             "chat_history": state.get("chat_history", ""),
#             "currency": state.get("currency", "USD"),
#             "cruise_search_info": state.get("cruise_search_info", CruiseSearchInfo()),
#             "action": "add_cart"}

async def general_infor_node(state: AgentState, config: dict) -> AgentState:
    logger.info(f"General infor node called with state: {state}")
    wrapped_model = wrap_model(model=model)
    response = await wrapped_model.ainvoke(state, config)
    logger.info(f"General infor node response: {response}")
    # cruise_id = state["current_cruise"]["id"]
    # if cruise_id is not None:
    #     cruise_infor_agent = await cruise_infor_tool.ainvoke(cruise_id, currency = state["currency"])
    #     cruises = [cruise_infor_agent]    
    # else:
    #     cruises = state["cruises"]
    return {"messages": [HumanMessage(content=response.content, name="general")],
            "cruises": state.get("cruises", []),
            "current_cruise": state.get("current_cruise", {}),
            "chat_history": state.get("chat_history", ""),
            "currency": state.get("currency", "USD"),
            "cruise_search_info": state.get("cruise_search_info", CruiseSearchInfo()),
            "action": "",
            "list_cabin": []}   

async def clear_context(state: AgentState, config: dict) -> AgentState:
    logger.info(f"Clear context node called with state: {state}")
    return {"messages":  [HumanMessage(content="Your context is clear now", name="clear_context")],
            "cruises": [],
            "current_cruise": {},
            "chat_history": "",
            "currency": "USD",
            "cruise_search_info": CruiseSearchInfo(),
            "action": "",
            "list_cabin": []}

def create_agent(use_tool = True, use_memory = True):
    agent = StateGraph(AgentState)
    agent.add_edge(START, "supervisor")
    agent.add_node("supervisor", supervisor_node)
    agent.add_node("cruise_search", cruise_search_node)
    agent.add_node("general_infor", general_infor_node)
    if use_tool:
        agent.add_node("db_query_tool", db_query_tool)
    agent.add_node("cruise_infor", cruise_infor_node)
    # agent.add_node("add_cart", add_cart_node)
    agent.add_node("clear_context", clear_context)

    if use_tool:
        agent.add_edge("cruise_search", "db_query_tool")
        agent.add_edge("db_query_tool", END)
    else:
        agent.add_edge("cruise_search", END)
    agent.add_edge("cruise_infor", END)
    # agent.add_edge("add_cart", END)
    agent.add_edge("clear_context", END)
    if use_memory:
        return agent.compile(checkpointer=MemorySaver())
    else:
        return agent.compile()

# import matplotlib.pyplot as plt
# from PIL import Image
# import io
# chatbot = create_agent()

# plt.imshow(Image.open(io.BytesIO(chatbot.get_graph().draw_mermaid_png())))
# plt.show()
if __name__ == "__main__":
    import asyncio
    configurable = {
            "thread_id": 1
        }
    run_id = uuid4()
    config = {"configurable": configurable}
    kwargs = {
                "input": {"messages": [HumanMessage(content="I want to go to Lisbon in next June")],
                          "current_cruise": {"id": "6787671d9eced029e874702b"},
                          "currency": "USD"
                          },
                          
                "config": config,
            }
    kwargs2 = {
                "input": {"messages": [HumanMessage(content="I want to go to Vancouver instead")],
                          "current_cruise": {"id": "6787671d9eced029e874702b"},
                          "currency": "USD"
                          },
                "config": config,
            }
    # kwargs = {
    #         "input": {"messages": [HumanMessage(content="What is the price of this cruise?")],
    #                     "current_cruise": {"id": "6787671d9eced029e874702b"},
    #                     "cruises": []},
                        
    #         "config": RunnableConfig(
    #             configurable=configurable,
    #             run_id=run_id,
    #         ),
    #     }

    # response = asyncio.run(chatbot.ainvoke(**kwargs))
    # import pdb; pdb.set_trace()
    # response2 = asyncio.run(chatbot.ainvoke(**kwargs2))
    # print(response)
    # print(response2)
    kwargs = {
            "input": {"messages": [HumanMessage(content="Show me the list cabins of cruise")],
                        "current_cruise": {"id": "6787671e9eced029e8747030"},
                        "currency": "USD"
                        },
                        
            "config": config,
        }
    
    chatbot = create_agent()
    response = asyncio.run(chatbot.ainvoke(**kwargs))
    print(response)

