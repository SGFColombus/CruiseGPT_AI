import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from langchain_openai import ChatOpenAI
from agent.tools.db.db import DBTool
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
from exceptions import NotFound
from pydantic import BaseModel, Field
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain.prompts import ChatPromptTemplate
from agent.tools.db.db import DBTool, CabinItem
from agent.tools.db.schema.order_item import OrderIn
from typing import Annotated
from langgraph.prebuilt import InjectedState
from langchain_core.runnables.config import RunnableConfig

from langgraph.types import Command, interrupt
from langgraph.graph import START, StateGraph
from langchain_core.tools.base import InjectedToolCallId
from langgraph.prebuilt import tools_condition, ToolNode
from agent.prompts.cruise_agent_prompt import (
    cruise_assistant_prompt,
    cruise_router_prompt,
    cruise_search_prompt,
    payment_infor_extract_prompt,
)

db_tool = DBTool()
llm = ChatOpenAI(model="gpt-4o", temperature=0.5)


@tool
def provide_cruise_detail(
    cruise_id: str | None,
    tool_call_id: Annotated[str, InjectedToolCallId],
):
    """Get the cruise detail of the current cruise such as price, duration, stops, etc, but exclude cabin.
    Args:
        cruise_id: The id of the cruise
        currency: The currency of the cruise
        tool_call_id: The id of the tool call
    Returns:
        The cruise detail
    """
    if cruise_id is None:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content="Please specify which cruise you want to see detail",
                        tool_call_id=tool_call_id,
                    )
                ],
                "action": "",
            }
        )
    cruise_detail = db_tool.get_cruise_infor(cruise_id, currency="USD")

    return Command(
        update={
            "messages": [ToolMessage(content=cruise_detail, tool_call_id=tool_call_id)],
            "action": "",
            "list_cruises": [],
        }
    )


@tool
def add_cabin_to_cart(
    cruise_id: str,
    cabin_name: str,
    state: Annotated[AgentState, InjectedState],
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
):
    """Call API for adding cabin cruise to user'cart. Cabin can be added multiple times.
    Args:
        cruise_id: The id of the cruise
        cabin_name: The name/description of cabin
    Returns:
        The cruise detail
    """
    cabin_item = CabinItem(
        cruiseId=cruise_id,
        description=cabin_name,
        currency=state.currency,
        quantity=1,
    )
    try:
        user_id = config.get("configurable", {}).get("user_id")
        list_cabins = []
        db_list_cabins = db_tool.get_list_cabin(state.current_cruise_id, state.currency)
        list_descriptions = [cabin["description"] for cabin in db_list_cabins]
        if state.current_cabin not in list_descriptions:
            raise NotFound(f"Cabin {state.current_cabin} not found in the cruise")
        cruise_info = db_tool.get_cruise_infor(state.current_cruise_id, state.currency)
        added_cabin = None
        if user_id is not None:
            try:
                added_cabin = db_tool.save_cabin_to_cart(
                    user_id=user_id,
                    cabin_item=cabin_item,
                )
                message = f"add cabin {str(added_cabin)} successfully"
            except ValueError as e:
                message = f"failed to to cabin: {str(e)}"
        else:
            added_cabin = [
                cabin
                for cabin in db_list_cabins
                if cabin["description"] == state.current_cabin
            ][0]
            message = f"add cabin {state.current_cabin} successfully"
        # add cruise info to cabin object
        if added_cabin is not None:
            added_cabin["imagesUrl"] = cruise_info.get("imagesUrl", [])
            added_cabin["sailEndDate"] = cruise_info.get("sailEndDate", None)
            added_cabin["sailStartDate"] = cruise_info.get("sailStartDate", None)
            list_cabins += [added_cabin]

    except NotFound as e:
        message = e
    except Exception as e:
        message = f"failed to cabin {state.current_cabin} {str(e)}"

    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=message,
                    tool_call_id=tool_call_id,
                )
            ],
            "action": "add_cart",
            "list_cabins": list_cabins,
        }
    )


@tool
def cancel_cabin_from_cart(
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
    cruise_id: str | None,
    currency: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
):
    """Get list of cabin in the current cruise.
    Args:
        cruise_id: The id of the cruise
        currency: The currency of the cruise
        tool_call_id: The id of the tool call
    Returns:
        The list of cabin in the current cruise
    """
    if cruise_id is None:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content="Please specify which cruise you want to see cabin",
                        tool_call_id=tool_call_id,
                    )
                ],
                "action": "",
            }
        )
    list_cabins = db_tool.get_list_cabin(cruise_id, currency)

    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=str(list_cabins),
                    tool_call_id=tool_call_id,
                )
            ],
            "action": "list_cabin",
            "list_cabins": list_cabins,
            "list_cruises": [],
        }
    )


@tool
def get_cart_detail(
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
):
    """
    Purpose:
        Query information of user's cart.
    Usage:
        - Use this tool when the user ask for their cart, cabin booked.
    """
    user_id = config.get("configurable", {}).get("user_id")
    if user_id is None:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content="Please login to see your cart",
                        tool_call_id=tool_call_id,
                    )
                ],
                "action": "",
            }
        )
    cart = db_tool.get_user_cart(user_id)
    return Command(
        update={
            "messages": [ToolMessage(content=str(cart), tool_call_id=tool_call_id)],
            # "action": "show_cart",
        }
    )


@tool
def get_orders_detail(
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
):
    """
    Purpose:
        Query information of user's payment history/orders.
    Usage:
        - Use this tool when the user ask for their orders/ payments.
    """
    user_id = config.get("configurable", {}).get("user_id")
    if user_id is None:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content="Please login to see your cart",
                        tool_call_id=tool_call_id,
                    )
                ],
                "action": "",
            }
        )
    orders = db_tool.get_user_orders(user_id)
    return Command(
        update={
            "messages": [ToolMessage(content=str(orders), tool_call_id=tool_call_id)],
            # "action": "show_cart",
        }
    )


@tool
def payment(
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
):
    """
    Purpose:
        Process the user's payment to their cabin cart.

    Usage:
        - Use this tool when the user indicates a desire to "make a payment" or complete their purchase.
        - Ensure that the payment process is initiated directly using the parameters from the state graph.

    Instructions:
        - All necessary information is already provided via the state graph; do not ask for additional details.
    """
    confirm_message = llm.invoke(
        f"Politely ask the user to confirm to continue with the payment. \n\n IMPORTANT: Your language must be matched with user's language. \n\n User's language: {state.language}"
    )
    user_confirm = interrupt(confirm_message.content)
    do_continue = llm.invoke(
        [
            SystemMessage(
                content="Based on user's reponse, determine if the payment should be continued. Respond with exactly yes or no, do not add any additional information."
            ),
            HumanMessage(content=user_confirm),
        ]
    )
    return Command(
        update={
            "messages": [
                ToolMessage(content=confirm_message.content, tool_call_id=tool_call_id),
                HumanMessage(content=user_confirm),
            ],
            "action": ("show_user_form" if do_continue.content == "yes" else ""),
            "func_routing": (
                "passenger_info" if do_continue.content == "yes" else "cruise_assistant"
            ),
        },
    )


tools = [
    provide_cruise_detail,
    add_cabin_to_cart,
    cancel_cabin_from_cart,
    get_list_cabin_in_cruise,
    get_cart_detail,
    get_orders_detail,
]


class NodeRoute(BaseModel):
    step: Literal["cruise_search", "cruise_assistant"] = Field(
        None, description=" The next step in the routing process"
    )


node_router = llm.with_structured_output(NodeRoute)


def supervisor_node(state: AgentState, config: dict):
    routing_node = node_router.invoke(
        [SystemMessage(content=cruise_router_prompt)] + state.messages
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
    prune_list_cruises = [
        {"id": cruise["id"], "name": cruise["name"]} for cruise in list_cruises
    ]
    total_number_of_cruises = len(prune_list_cruises)
    list_cruises = list_cruises[:5]  ## Only take 5
    response = llm.invoke(
        [
            SystemMessage(content=cruise_search_prompt),
            AIMessage(
                content=f"\n\nUser Preferences: {user_preferences}\n\n Example found cruises: {list_cruises}\n\nTotal  cruises found: {total_number_of_cruises}"
            ),
        ]
    )

    return {
        "messages": [AIMessage(content=str(prune_list_cruises)), response],
        "list_cruises": list_cruises,
        "list_cabins": [],
        "action": "show_cruises",
    }


def assistant(state: AgentState):
    cruise_assistant_prompt_with_current_cruise_id = cruise_assistant_prompt.format(
        current_cruise_id=state.current_cruise_id,
        current_cabin=state.current_cabin,
    )
    llm_with_tools = llm.bind_tools([*tools, payment], parallel_tool_calls=False)
    return {
        "messages": [
            llm_with_tools.invoke(
                [SystemMessage(content=cruise_assistant_prompt_with_current_cruise_id)]
                + state.messages
            )
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


def passenger_info_node(state: AgentState, config: dict):
    confirm_message = llm.invoke(
        [
            SystemMessage(
                f"Politely ask the user about their passenger information. \n\n IMPORTANT: Your language must be matched with user's language. \n\n User's language: {state.language}"
            )
        ]
        + state.messages
    )
    passenger_info = interrupt(confirm_message.content)

    infor_extractor = llm.with_structured_output(OrderIn)
    order: OrderIn = infor_extractor.invoke(
        [
            SystemMessage(payment_infor_extract_prompt),
            HumanMessage(content=passenger_info),
        ]
    )
    order.userId = config.get("configurable", {}).get("user_id")

    try:
        db_tool.save_order(order)
        message = "Order saved successfully"

        return Command(
            update={
                "messages": [
                    HumanMessage(content=passenger_info),
                    AIMessage(content=message),
                ],
                "action": "",
                "func_routing": "cruise_assistant",
            },
        )
    except:
        message = "Failed to save order"
        return Command(
            update={
                "messages": [
                    HumanMessage(content=passenger_info),
                    AIMessage(content=message),
                ],
                "action": "",
                "func_routing": "payment_failed",
            },
        )


def payment_failed(state: AgentState, config: dict):
    confirm_message = llm.invoke(
        # [
        [
            SystemMessage(
                f"Politely reply to user why payment failed. Ask them if they want to process again. Keep it short and concise. Do not add any additional information. \n\n IMPORTANT: Your language must be matched with user's language. \n\n User's language: {state.language}"
            )
        ]
        + state.messages[-2:]
    )
    user_confirm = interrupt(confirm_message.content)
    do_continue = llm.invoke(
        [
            SystemMessage(
                content="Based on user's reponse, determine if the payment should be continued. Respond with exactly yes or no, do not add any additional information. If user's reponse, is not relevant to payment, respond with no."
            ),
            HumanMessage(content=user_confirm),
        ]
    )
    return Command(
        update={
            "messages": [
                AIMessage(content=confirm_message.content),
                HumanMessage(content=user_confirm),
            ],
            "action": ("show_user_form" if do_continue.content == "yes" else ""),
            "func_routing": (
                "passenger_info" if do_continue.content == "yes" else "cruise_assistant"
            ),
        },
    )


def build_cruise_agent():
    cruise_agent = StateGraph(AgentState)
    cruise_agent.add_node("cruise_supervisor", supervisor_node)
    cruise_agent.add_node("cruise_search", cruise_search_node)
    cruise_agent.add_node("cruise_assistant", assistant)
    cruise_agent.add_node("payment", ToolNode([payment]))
    cruise_agent.add_node("passenger_info", passenger_info_node)
    cruise_agent.add_node("payment_failed", payment_failed)

    cruise_agent.add_node("tools", ToolNode(tools))

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
        ["cruise_assistant", "passenger_info"],
    )
    cruise_agent.add_conditional_edges(
        "passenger_info",
        lambda state, config: state.func_routing,
        ["payment_failed", "cruise_assistant"],
    )
    cruise_agent.add_conditional_edges(
        "payment_failed",
        lambda state, config: state.func_routing,
        ["passenger_info", "cruise_assistant"],
    )
    cruise_agent.add_edge("tools", "cruise_assistant")
    cruise_agent.add_edge("cruise_search", END)

    cruise_agent.set_entry_point("cruise_supervisor")

    cruise_agent = cruise_agent.compile(checkpointer=MemorySaver())
    return cruise_agent


def test(cruise_agent):
    config = {"configurable": {"thread_id": 1, "user_id": "67bc43923f9f1b182eb81908"}}
    messages = [
        # "any cruise to Europe?",
        # "any cruise to Vancouver?",
        # "what cabins do u have?",
        # "what want to add 1st cabin to my cart?",
        # "I want to pay now",
        "what cabin do u have?",
        "I want to add current_cabin to cart",
    ]
    for message in messages:
        message = HumanMessage(content=message)
        message.pretty_print()
        messages = cruise_agent.invoke(
            input={
                "messages": [message],
                "current_cruise_id": "678767209eced029e874703d",
                "current_cabin": "Classic Veranda Suite",
            },
            config=config,
        )
        snapshot = cruise_agent.get_state(config)
        while snapshot.next:
            ai_message = snapshot.tasks[0].interrupts[0].value
            value_from_human = "yes"
            messages = cruise_agent.invoke(
                Command(resume=value_from_human), config=config
            )
            snapshot = cruise_agent.get_state(config)
        # messages["messages"][-1].pretty_print()
        print(messages["messages"])


cruise_agent = build_cruise_agent()
if __name__ == "__main__":
    # main()
    # import time

    # config = {"configurable": {"thread_id": 1, "user_id": "67bc43923f9f1b182eb81908"}}
    # messages = cruise_agent.invoke(
    #     input={
    #         "messages": ["add current cabin to cart"],
    #         "current_cruise_id": "678767209eced029e874703d",
    #         "current_cabin": "Classic Veranda Suite",
    #     },
    #     config=config,
    # )
    # print(messages)

    # start_time = time.time()
    # test(cruise_agent)
    # end_time = time.time()
    # print(f"Total Time taken: {end_time - start_time} seconds")
    config = {"configurable": {"thread_id": 1, "user_id": "67bc43923f9f1b182eb81908"}}
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
                "current_cruise_id": "678767209eced029e874703d",
                "current_cabin": "Classic Veranda Suite",
                # "currency": "USD",
                # "country": "AU",
            },
            config=config,
        )
        snapshot = cruise_agent.get_state(config)
        while snapshot.next:
            print(snapshot.values)
            ai_message = snapshot.tasks[0].interrupts[0].value
            value_from_human = input(f"{ai_message}:\n")
            messages = cruise_agent.invoke(
                Command(resume=value_from_human), config=config
            )
            snapshot = cruise_agent.get_state(config)
        messages["messages"][-1].pretty_print()
