from agent.tools.db import DBTool
from langchain_core.tools import tool
import json
from langchain_core.messages import ToolMessage, HumanMessage
from agent.objects.objects import CruiseSearchInfo, AgentState

db_tool = DBTool()


@tool
async def db_query_tool(
    cruise_search_info: CruiseSearchInfo = None,
    currency: str = "USD",
    country: str = "US",
):
    """
    Execute a SQL query against the database and get back the result.
    If the query is not correct, an error message will be returned.
    If an error is returned, rewrite the query, check the query, and try again.
    """
    preferences = dict(cruise_search_info)
    print(f"Successfully parsed preferences: {preferences}")
    result = await db_tool.get_cruises(preferences, currency=currency, country=country)
    if len(result["cruises"]) == 0:
        return {
            "messages": [
                HumanMessage(
                    content="I'm sorry, I couldn't find any cruises that match your preferences. Please try again with different criteria."
                )
            ],
            "cruises": [],
        }
    if not result:
        return {
            "messages": [
                HumanMessage(
                    content="I'm sorry, I couldn't find any cruises that match your preferences. Please try again with different criteria."
                )
            ],
            "cruises": [],
        }
        # return "Error: Query failed. Please rewrite your query and try again."
    return {
        "messages": [HumanMessage(content=result["message"])],
        "cruises": result["cruises"],
    }
    # return ToolMessage(content=json.dumps(result))


@tool
async def enrich_preferences(messages: list, currency: str = "USD"):
    """
    Enrich the preferences with the cruise information.
    """
    analysis_response = messages[-1].content
    content = analysis_response.strip()
    preferences = json.loads(content)
    return {
        "messages": [HumanMessage(content=preferences["message"])],
        "cruises": [preferences],
    }


# create a tool to get cruise infor
@tool
async def cruise_infor_tool(cruise_id: str, currency: str = "USD"):
    """
    Get the information of a cruise.
    """
    return await db_tool.get_cruise_infor(cruise_id, currency)


@tool
async def get_cabin_tool(cruise_id: str, currency: str = "USD"):
    """
    Get the cabin information of a cruise.
    """
    return await db_tool.get_list_cabin(cruise_id, currency)


if __name__ == "__main__":
    import asyncio

    result = asyncio.run(
        db_query_tool.invoke(
            '{\n    "destinations": ["Tokyo"],\n    "minDuration": null,\n    "maxDuration": null,\n    "departureAfter": "2025-05-01",\n    "departureBefore": "2025-05-31",\n    "maxPrice": null,\n    "preferences": [],\n    "message": "You would like to go to Tokyo. Would you like to travel in May 2025 as well, or do you have other dates in mind? Also, any preferences for the duration of the cruise?"\n}'
        )
    )
    print(result)
