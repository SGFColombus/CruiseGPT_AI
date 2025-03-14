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
    message: Optional[str] = None


class AgentState(MessagesState, total=False):
    """`total=False` is PEP589 specs.

    documentation: https://typing.readthedocs.io/en/latest/spec/typeddict.html#totality
    """
    messages: list[BaseMessage]
    cruises: list[dict] = []
    current_cruise: dict = {}
    next: str
    chat_history: str
    currency: str = "USD"
    action: str|None = None
    cruise_search_info: CruiseSearchInfo|None = None
    list_cabin: list[dict] = []
    description: str|None = None
