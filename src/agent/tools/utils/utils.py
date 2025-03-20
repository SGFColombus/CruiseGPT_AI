def enrich_cruise(cruise: dict, currency: str = "USD", country: str = "US"):
    itinerary = []
    for stop in cruise.get("itinerary", []):
        itinerary_dict = {}
        itinerary_dict["portName"] = stop.get("portName", "")
        itinerary_dict["description"] = stop.get("description", "")
        itinerary_dict["date"] = stop.get("date", "")
        itinerary.append(itinerary_dict)

    # get prices for each cruise
    prices = []
    for price in cruise.get("prices", []):
        if price.get("currency", "") != currency and (
            "US" not in price.get("countries", [])
        ):
            continue
        if "suiteRates" in price.keys():
            for suite_rate in price.get("suiteRates", []):
                for rate in suite_rate.get("rates", []):
                    price_dict = {}
                    price_dict["price"] = rate.get("price", None)
                    price_dict["suiteName"] = suite_rate.get("name", "")
                    price_dict["suiteDescription"] = suite_rate.get("description", "")
                    price_dict["originalPrice"] = rate.get("originalPrice", None)
                    price_dict["status"] = rate.get("status", "")
                    price_dict["fare"] = rate.get("fare", "")
                    prices.append(price_dict)
                # get available prices and sort by price
                available_prices = [
                    price
                    for price in prices
                    if (
                        price["fare"] == "P2P"
                        and price["status"] == "A"
                        and price["price"] is not None
                    )
                ]
                available_prices.sort(key=lambda x: x["price"])

        elif "suites" in price.keys():
            if len(price.get("suites", [])) > 0:
                for suite_price in price.get("suites", []):
                    price_dict = {}
                    price_dict["price"] = suite_price.get("price", None)
                    price_dict["suiteName"] = suite_price.get("name", "")
                    price_dict["suiteDescription"] = suite_price.get("description", "")
                    price_dict["originalPrice"] = suite_price.get("originalPrice", None)
                    price_dict["status"] = suite_price.get("status", "")
                    prices.append(price_dict)
                # get available prices and sort by price
                available_prices = [
                    price
                    for price in prices
                    if (price["status"] == "A" and price["price"] is not None)
                ]
                available_prices.sort(key=lambda x: x["price"])
        else:
            available_prices = []
            break

    # get cheapest suite
    cheapest_suite = available_prices[0] if len(available_prices) > 0 else None
    image_url = cruise.get("imagesUrl", "")
    enriched_cruise = {
        "id": str(cruise["_id"]),
        "name": cruise.get("title", ""),
        "destination": cruise.get("destination", ""),
        # "itinerary": " → ".join([f"{stop.get('portName', '')} - {stop.get('description', '')}" for stop in cruise["itinerary"]]),
        "itinerary": " → ".join(
            [f"{stop.get('portName', '')}" for stop in cruise["itinerary"]]
        ),
        "duration": cruise.get("duration", ""),
        "price": cheapest_suite["price"] if cheapest_suite else None,
        "originalPrice": cheapest_suite["originalPrice"] if cheapest_suite else None,
        "suiteName": (
            cheapest_suite["suiteName"] if cheapest_suite else "Standard Suite"
        ),
        "suiteDescription": (
            cheapest_suite["suiteDescription"] if cheapest_suite else None
        ),
        "image": (
            image_url[0]
            if isinstance(image_url, list) and len(image_url) > 0
            else image_url
        ),
        "departureDate": cruise.get("sailStartDate", ""),
        "returnDate": cruise.get("sailEndDate", ""),
        "shipName": cruise.get("shipName", ""),
        "embarkationPort": cruise.get("embarkationPortName", ""),
        "disembarkationPort": cruise.get("disembarkationPortName", ""),
        "mapUrl": cruise.get("mapUrl", ""),
    }
    return enriched_cruise


# import
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from typing import Literal, TypedDict
from langchain_core.language_models.chat_models import BaseChatModel


def wrap_model(
    model: BaseChatModel,
    system_prompt: str = "",
    structured_output: TypedDict = None,
    tools: list[BaseTool] = [],
) -> BaseChatModel:
    preprocessor = RunnableLambda(
        lambda state: [SystemMessage(content=system_prompt)] + state["messages"],
        name="StateModifier",
    )
    if tools:
        model = model.bind_tools(tools)
    if structured_output is not None:
        model = model.with_structured_output(structured_output)
    return preprocessor | model
