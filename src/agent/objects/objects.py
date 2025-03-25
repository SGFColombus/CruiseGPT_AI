# from pydantic import BaseModel
# from typing import List, Optional
from typing import Annotated
from langchain_core.messages import HumanMessage, AIMessage, AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

# from datetime import date
# from langchain_core.messages import BaseMessage
# from langgraph.graph import MessagesState


# class CruiseSearchInfo(BaseModel):
#     embarkationPort: Optional[List[str]] = None
#     disembarkationPort: Optional[List[str]] = None
#     destinations: Optional[List[str]] = None
#     minDuration: Optional[int] = None
#     maxDuration: Optional[int] = None
#     minSailStartDate: Optional[str] = None
#     maxSailStartDate: Optional[str] = None
#     minSailEndDate: Optional[str] = None
#     maxSailEndDate: Optional[str] = None
#     minPrice: Optional[float] = None
#     maxPrice: Optional[float] = None
#     round_trip: Optional[bool] = None
#     ignore_destinations: Optional[List[str]] = None
#     message: Optional[str] = None


# class AgentState(MessagesState, total=False):
#     """`total=False` is PEP589 specs.

#     documentation: https://typing.readthedocs.io/en/latest/spec/typeddict.html#totality
#     """

#     messages: list[BaseMessage]
#     cruises: list[dict] = []
#     current_cruise: dict = {}
#     next: str
#     chat_history: str
#     currency: str = "USD"
#     action: str | None = None
#     cruise_search_info: CruiseSearchInfo | None = None
#     list_cabin: list[dict] = []
#     description: str | None = None


# class MetaData(BaseModel):
#     currency: str = "USD"
#     country: str = "US"


# class UserPreferences(BaseModel):
#     departureAfter: date | None = None
#     departureBefore: date | None = None
#     destinations: list[str] = []
#     minPrice: int | None = (None,)
#     maxPrice: int | None = None
#     # price_discount: bool = False


# class AgentState(MessagesState):
#     # chat history
#     messages: list[BaseMessage]
#     # user metadata
#     metadata: MetaData
#     user_preferences: UserPreferences
#     # current search state
#     list_cruises: list[dict] = []
#     list_cabin: list[dict] = []

#     current_cruise: dict = {}
#     current_cabin: dict = {}
from pydantic import BaseModel
from typing import List, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph import MessagesState


class CruiseSearchInfo(BaseModel):
    embarkationPort: Optional[List[str]] = None
    disembarkationPort: Optional[List[str]] = None
    destinations: Optional[List[str]] = None
    minDuration: Optional[int] = None
    maxDuration: Optional[int] = None
    minSailStartDate: Optional[str] = None
    maxSailStartDate: Optional[str] = None
    minSailEndDate: Optional[str] = None
    maxSailEndDate: Optional[str] = None
    minPrice: Optional[float] = None
    maxPrice: Optional[float] = None
    round_trip: Optional[bool] = None
    price_discount: Optional[bool] = None
    ignore_destinations: Optional[List[str]] = None
    # message: Optional[str] = None


class AgentState(BaseModel):
    """The state of the agent."""

    messages: Annotated[list[AnyMessage], add_messages]
    chat_history: str | None = None
    currency: str = "USD"
    action: str = ""
    cruise_search_info: CruiseSearchInfo | None = None
    list_cruises: list[dict] = []
    list_cabins: list[dict] = []
    current_cruise_id: str | None = None
    current_cabin: str | None = None

    agent_routing: str | None = None
    func_routing: str | None = None
