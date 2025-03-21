import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from langchain_openai import ChatOpenAI
from agent.tools.db import DBTool
from typing import Annotated
from langchain_core.tools import tool
from agent.objects.objects import AgentState, CruiseSearchInfo
from langgraph.prebuilt import InjectedState
from agent.prompts.exact_infor_prompt import extract_infor_promt, context_infor_cruise
from agent.objects.objects import AgentState, CruiseSearchInfo
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
import logging
from typing import Literal, TypedDict
from agent.tools.utils.utils import wrap_model
import asyncio
from pydantic import BaseModel, Field
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain.prompts import ChatPromptTemplate
from agent.tools.db import DBTool
from typing import Annotated
from langgraph.prebuilt import InjectedState

from langgraph.types import Command
from langgraph.graph import START, StateGraph
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import tools_condition, ToolNode
from agent.prompts.cruise_agent_prompt import (
    cruise_assistant_prompt,
    cruise_router_prompt,
    cruise_search_prompt,
)

db_tool = DBTool()
llm = ChatOpenAI(model="gpt-4o", temperature=0.5)


@tool
def provide_cruise_detail(
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
):
    """Get the cruise detail of the current cruise such as price, duration, stops, etc, but exclude cabin."""
    cruise_id = state.current_cruise["id"]
    currency = state.currency
    cruise_detail = db_tool.get_cruise_infor(cruise_id, currency)

    return Command(
        update={
            "messages": [ToolMessage(content=cruise_detail, tool_call_id=tool_call_id)],
            "action": "",
        }
    )


@tool
def add_cabin_to_cart(
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
):
    """Add current cabin to the cart."""
    list_cabins = state.list_cabins
    list_cabins = [cabin for cabin in list_cabins if cabin["description"] == state.description]

    return Command(
        update={
            "messages": [
                ToolMessage(
                    content="Cabin added to cart successfully",
                    tool_call_id=tool_call_id,
                )
            ],
            "action": "add_cart",
            "list_cabins": list_cabins,
        }
    )


@tool
def cancel_cabin_from_cart(
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
):
    """Cancel a cabin from the cart."""

    return Command(
        update={
            "messages": [
                ToolMessage(
                    content="Cabin successfully removed from cart",
                    tool_call_id=tool_call_id,
                )
            ],
            "action": "remove_cart",
        }
    )


@tool
def get_list_cabin_in_cruise(
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
):
    """Get list of cabin in the current cruise."""
    cruise_id = state.current_cruise["id"]
    currency = state.currency
    list_cabin = db_tool.get_list_cabin(cruise_id, currency)

    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=str(list_cabin),
                    tool_call_id=tool_call_id,
                )
            ],
            "action": "list_cabin",
            "list_cabins": list_cabin,
            "list_cruises": [],
        }
    )


tools = [
    provide_cruise_detail,
    add_cabin_to_cart,
    cancel_cabin_from_cart,
    get_list_cabin_in_cruise,
]


llm_with_tools = llm.bind_tools(tools, parallel_tool_calls=False)


class NodeRoute(BaseModel):
    step: Literal["cruise_search", "cruise_assistant"] = Field(
        None, description=" The next step in the routing process"
    )


node_router = llm.with_structured_output(NodeRoute)


def supervisor_node(state: AgentState, config: dict):
    routing_node = node_router.invoke(
        [
            SystemMessage(content=cruise_router_prompt),
            state.messages[-1],
        ]
    )
    return {"func_routing": routing_node.step}


def routing(state: AgentState, config: dict):
    routing_node = state.func_routing
    return routing_node


def cruise_search_node(state: AgentState, config: dict) -> AgentState:
    model_with_structured_output = llm.with_structured_output(CruiseSearchInfo)
    wrapped_model = wrap_model(
        model=model_with_structured_output,
        system_prompt=extract_infor_promt(state.cruise_search_info),
    )
    user_preferences = wrapped_model.invoke(state, config)
    list_cruises = db_tool.get_cruises(user_preferences.model_dump())
    response = llm.invoke(
        [
            SystemMessage(content=cruise_search_prompt),
            AIMessage(content=f"Result cruises found: {list_cruises}"),
            HumanMessage(content=f"User preference: {user_preferences}"),
        ]
    )

    return {
        "messages": [response],
        "list_cruises": list_cruises,
        "list_cabins": [],
    }


def assistant(state: AgentState):
    return {
        "messages": [
            llm_with_tools.invoke(
                [SystemMessage(content=cruise_assistant_prompt)] + state.messages
            )
        ],
    }


def build_cruise_agent():
    cruise_agent = StateGraph(AgentState)
    cruise_agent.add_node("cruise_supervisor", supervisor_node)
    cruise_agent.add_node("cruise_search", cruise_search_node)
    cruise_agent.add_node("cruise_assistant", assistant)
    cruise_agent.add_node("tools", ToolNode(tools))

    cruise_agent.add_edge(START, "cruise_supervisor")
    cruise_agent.add_conditional_edges(
        "cruise_supervisor",
        routing,
        {
            "cruise_search": "cruise_search",
            "cruise_assistant": "cruise_assistant",
        },
    )
    cruise_agent.add_conditional_edges(
        "cruise_assistant",
        tools_condition,
    )
    cruise_agent.add_edge("tools", "cruise_assistant")
    cruise_agent.add_edge("cruise_search", END)
    # cruise_agent.add_edge("cruise_assistant", END)

    cruise_agent = cruise_agent.compile(checkpointer=MemorySaver())
    return cruise_agent


def test(cruise_agent):
    configurable = {"thread_id": 1}
    config = {"configurable": configurable}

    message_list = [
        "Tell me about the cruise",
        "What is this price?",
        "Tell me about the cabin",
        "Does this cruise visit Hanoi?",
        "I want to book this cabin",
        "I want to cancel a cabin",
    ]

    for message in message_list:
        messages = [
            HumanMessage(content=message),
        ]
        messages[-1].pretty_print()
        messages = cruise_agent.invoke(
            input={
                "messages": messages,
                "current_cruise": {"id": "6787671e9eced029e8747030"},
            },
            config=config,
        )
        # for m in messages["messages"]:
        #     m.pretty_print()
        messages["messages"][-1].pretty_print()


if __name__ == "__main__":
    # main()
    cruise_agent = build_cruise_agent()
    test(cruise_agent)
