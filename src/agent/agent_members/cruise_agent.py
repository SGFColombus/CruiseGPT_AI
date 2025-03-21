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

from langgraph.types import Command, interrupt
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
    """Add a cabin to the cart."""

    return Command(
        update={
            "messages": [
                ToolMessage(
                    content="Cabin added to cart successfully",
                    tool_call_id=tool_call_id,
                )
            ],
            "action": "add_cart",
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


@tool
def payment(
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
):
    """
    Purpose:
        Process the user's payment to complete a purchase.

    Usage:
        - Use this tool when the user indicates a desire to "make a payment" or complete their purchase.
        - Ensure that the payment process is initiated directly using the parameters from the state graph.

    Instructions:
        - All necessary information is already provided via the state graph; do not ask for additional details.
    """
    confirm_message = llm.invoke(
        "Politely ask the user to confirm to continue with the payment."
    )
    value = interrupt(confirm_message.content)
    do_continue = llm.invoke(
        [
            SystemMessage(
                content="Based on user's reponse, determine if the payment should be continued. Respond with exactly yes or no, do not add any additional information."
            ),
            HumanMessage(content=value),
        ]
    )

    return {
        "func_routing": (
            "passenger_info_node" if do_continue == "yes" else "cruise_assistant"
        ),
        "messages": [
            AIMessage(content=confirm_message.content),
            HumanMessage(content=value),
        ],
    }


tools = [
    provide_cruise_detail,
    add_cabin_to_cart,
    cancel_cabin_from_cart,
    get_list_cabin_in_cruise,
]


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
    llm_with_tools = llm.bind_tools([*tools, payment], parallel_tool_calls=False)
    return {
        "messages": llm_with_tools.invoke(
            [SystemMessage(content=cruise_assistant_prompt)] + state.messages
        )
    }


# class YesNoRouter(TypedDict):
#     _next: Literal["yes", "no"]


# def payment_routing_decision(user_message: str) -> str:
#     """
#     Uses an LLM to decide if the payment should be approved.
#     The prompt instructs the LLM to respond with exactly yes or no.
#     """
#     prompt = f"Based on user's reponse, determine if the payment should be continued. "
#     llm_router = llm.with_structured_output(YesNoRouter)
#     decision = llm_router.invoke(
#         [SystemMessage(content=prompt), HumanMessage(content=user_message)]
#     )
#     return decision["_next"]


def passenger_info_node(state: AgentState, config: dict):
    action_instruction = llm.invoke(
        "Politely ask the user about their passenger information."
    )
    value = interrupt(action_instruction.content)
    return {
        "messages": [
            AIMessage(content=action_instruction.content),
            HumanMessage(content=value),
        ],
    }


def assistant_route_tools(state: AgentState, config: dict):
    next_node = tools_condition(state)
    if next_node == END:
        return END
    ai_message = state.messages[-1]
    first_tool_call = ai_message.tool_calls[0]
    if first_tool_call["name"] == "payment":
        return "payment"
    return "tools"


def build_cruise_agent():
    cruise_agent = StateGraph(AgentState)
    cruise_agent.add_node("cruise_supervisor", supervisor_node)
    cruise_agent.add_node("cruise_search", cruise_search_node)
    cruise_agent.add_node("cruise_assistant", assistant)
    cruise_agent.add_node("payment", ToolNode([payment]))
    cruise_agent.add_node("tools", ToolNode(tools))
    cruise_agent.add_node("passenger_info", passenger_info_node)

    cruise_agent.add_conditional_edges(
        "cruise_supervisor",
        lambda state, config: state.func_routing,
        ["cruise_search", "cruise_assistant"],
    )
    cruise_agent.add_conditional_edges(
        "cruise_assistant", assistant_route_tools, ["tools", "payment", END]
    )
    cruise_agent.add_conditional_edges(
        "payment",
        lambda state, config: state.func_routing,
        ["passenger_info", "cruise_assistant"],
    )
    cruise_agent.add_edge("tools", "cruise_assistant")
    cruise_agent.add_edge("passenger_info", "cruise_assistant")
    cruise_agent.add_edge("cruise_search", END)

    cruise_agent.set_entry_point("cruise_supervisor")

    cruise_agent = cruise_agent.compile(checkpointer=MemorySaver())
    return cruise_agent


cruise_agent = build_cruise_agent()
if __name__ == "__main__":
    # main()
    # test(cruise_agent)
    configurable = {"thread_id": 1}
    config = {"configurable": configurable}
    while True:
        try:
            user_input = input("\nYou: ")
        except (EOFError, KeyboardInterrupt):
            print("\nExiting chat.")
            break

        if user_input.strip().lower() in ["exit", "quit", "q"]:
            print("👋 Goodbye!")
            break
        messages = cruise_agent.invoke(
            input={
                "messages": [HumanMessage(content=user_input)],
                "current_cruise": {"id": "678767209eced029e874703d"},
                "currency": "USD",
                "country": "AU",
            },
            config=config,
        )
        snapshot = cruise_agent.get_state(config)
        while snapshot.next:
            ai_message = snapshot.tasks[0].interrupts[0].value
            value_from_human = input(f"{ai_message}:\n")
            messages = cruise_agent.invoke(
                Command(resume=value_from_human), config=config
            )
            snapshot = cruise_agent.get_state(config)
        messages["messages"][-1].pretty_print()
