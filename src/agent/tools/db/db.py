import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "../../.."))
import os
from pymongo import MongoClient, ReturnDocument
import dotenv
from datetime import datetime
import re
from bson import ObjectId
from agent.tools.db.schema.cabin_item import CabinItem
from agent.tools.db.schema.order_item import ContactInfo, OrderIn
from datetime import datetime, timezone

from agent.tools.utils.utils import enrich_cruise

dotenv.load_dotenv()


class DBTool:
    def __init__(self):
        self.client = MongoClient(os.getenv("MONGODB_URI"))
        self.db = self.client["silversea_cruises"]
        self.collection = self.db["cruises"]
        self.history_collection = self.db["chathistories"]

    def get_cruises(self, preferences, currency: str = "USD", country: str = "US"):
        if preferences.get("minSailStartDate") is None:
            preferences["minSailStartDate"] = datetime.now().strftime("%Y-%m-%d")
            # preferences["minSailStartDate"] = datetime.now().isoformat()

        # Build query object properly
        query = {}

        # Handle date range query
        date_conditions = {}
        date_conditions["$gte"] = datetime.strptime(
            preferences["minSailStartDate"], "%Y-%m-%d"
        ).strftime("%Y-%m-%d")
        # date_conditions["$gte"] = datetime.fromisoformat(preferences["minSailStartDate"])

        if preferences.get("maxSailStartDate") is not None:
            date_conditions["$lte"] = datetime.strptime(
                preferences["maxSailStartDate"], "%Y-%m-%d"
            ).strftime("%Y-%m-%d")
            # date_conditions["$lte"] = datetime.fromisoformat(preferences["maxSailStartDate"])
        query["sailStartDate"] = date_conditions

        return_date_conditions = {}
        if preferences.get("minSailEndDate") is not None:
            return_date_conditions["$gte"] = datetime.strptime(
                preferences["minSailEndDate"], "%Y-%m-%d"
            ).strftime("%Y-%m-%d")
            # return_date_conditions["$gte"] = datetime.fromisoformat(preferences["minSailEndDate"])
        if preferences.get("maxSailEndDate") is not None:
            return_date_conditions["$lte"] = datetime.strptime(
                preferences["maxSailEndDate"], "%Y-%m-%d"
            ).strftime("%Y-%m-%d")
            # return_date_conditions["$lte"] = datetime.fromisoformat(preferences["maxSailEndDate"])
        if len(return_date_conditions.keys()) > 0:
            query["sailEndDate"] = return_date_conditions

        # Handle destinations query (unchanged)
        if (preferences.get("destinations", []) is not None) and len(
            preferences.get("destinations", [])
        ) > 0:
            search_terms = [
                re.compile(dest.strip(), re.IGNORECASE)
                for dest in preferences["destinations"]
            ]
            query["$or"] = [
                {"destination": {"$in": search_terms}},
                {"embarkationPortName": {"$in": search_terms}},
                {"disembarkationPortName": {"$in": search_terms}},
                {"itinerary.portName": {"$in": search_terms}},
            ]
        if (preferences.get("embarkationPort", []) is not None) and len(
            preferences.get("embarkationPort", [])
        ) > 0:
            query["embarkationPortName"] = {"$in": preferences["embarkationPort"]}
        if (preferences.get("disembarkationPort", []) is not None) and len(
            preferences.get("disembarkationPort", [])
        ) > 0:
            query["disembarkationPortName"] = {"$in": preferences["disembarkationPort"]}
        # Handle duration range query
        duration_conditions = {}
        if preferences.get("minDuration") is not None:
            duration_conditions["$gte"] = preferences["minDuration"]
        if preferences.get("maxDuration") is not None:
            duration_conditions["$lte"] = int(preferences["maxDuration"])
        if duration_conditions:
            query["duration"] = duration_conditions
        if preferences.get("round_trip") is True:
            query["$expr"] = {
                "$eq": ["$disembarkationPortName", "$embarkationPortName"]
            }
        if (
            preferences.get("ignore_destinations") is not None
            and len(preferences.get("ignore_destinations")) > 0
        ):
            search_terms = [
                re.compile(dest.strip(), re.IGNORECASE)
                for dest in preferences.get("ignore_destinations")
            ]
            # Assuming the field to check is named "destination"
            # query["destination"] = {"$not": {"$in": search_terms}}
            query["itinerary.portName"] = {"$nin": search_terms}
        # price conditions
        price_negative_conditions = []
        if preferences.get("minPrice") is not None:
            price_negative_conditions.append(
                {"price": {"$lte": preferences["minPrice"]}}
            )
        if preferences.get("maxPrice") is not None:
            price_negative_conditions.append(
                {"price": {"$gte": preferences["maxPrice"]}}
            )
        if price_negative_conditions:
            query["prices"] = {
                "$elemMatch": {
                    "currency": currency,
                    "countries": country,
                    "suiteRates.rates": {
                        "$elemMatch": {
                            "status": "A",
                            "fare": "P2P",
                        },
                        "$not": {
                            "$elemMatch": {
                                "$or": price_negative_conditions,
                            }
                        },
                    },
                }
            }
        # price discount conditions
        if preferences.get("price_discount") is True:
            query["prices.suiteRates.rates.priceStatus"] = "D"

        # Fix sort syntax
        cruises = list(self.collection.find(query).sort("sailStartDate", 1))

        enriched_cruises = []
        for cruise in cruises:
            enriched_cruise = enrich_cruise(cruise, currency, country)
            if enriched_cruise["price"] is None:
                continue
            enriched_cruises.append(enriched_cruise)
        return enriched_cruises

    def get_cruise_infor(self, cruise_id, currency: str = "USD", country: str = "US"):
        cruise = self.collection.find_one({"_id": ObjectId(cruise_id)})
        enriched_cruise = enrich_cruise(cruise, currency, country)
        return enriched_cruise

    def get_list_cabin(self, cruise_id, currency: str = "USD", country: str = "US"):
        cruise = self.collection.find_one({"_id": ObjectId(cruise_id)})
        list_cabin = []
        for price in cruise.get("prices", []):
            if price.get("currency", "") == currency and (
                country in price.get("countries", [])
            ):
                for suiteRate in price.get("suiteRates", []):
                    for rate in suiteRate.get("rates", []):
                        if (
                            rate.get("status", "") == "A"
                            and rate.get("fare", "") == "P2P"
                            and rate.get("price", None) is not None
                        ):
                            list_cabin.append(
                                {
                                    "cruise_id": cruise_id,
                                    "title": cruise.get("title", ""),
                                    "name": suiteRate.get("name", ""),
                                    "description": suiteRate.get("description", ""),
                                    "fare": rate.get("fare", ""),
                                    "price": rate.get("price", None),
                                    "priceStatus": rate.get("priceStatus", ""),
                                    "originalPrice": rate.get("originalPrice", None),
                                    "cabinUrl": suiteRate.get("cabinUrl", ""),
                                    "imagesUrl": cruise.get("imagesUrl", []),
                                    "sailEndDate": cruise.get("sailEndDate", None),
                                    "sailStartDate": cruise.get("sailStartDate", None),
                                }
                            )
        return list_cabin

    def ingest_history(
        self, session_id, message, sender, cruise_list=[], list_cabin=[]
    ):
        chat_history = self.history_collection.find_one({"sessionId": session_id})
        cruises = []
        for cruise in cruise_list:
            cruises.append(ObjectId(cruise))
        message = {
            "sender": sender,
            "text": message,
            "timestamp": datetime.now(),
            "cruises": cruises,
            "cabins": list_cabin,
        }
        if chat_history is None:
            return None
        chat_history["messages"].append(message)
        self.history_collection.update_one(
            {"sessionId": session_id}, {"$set": {"messages": chat_history["messages"]}}
        )

    def get_history(self, session_id):
        chat_history = []
        chat_history = self.history_collection.find_one({"sessionId": session_id})
        message_history = []
        if chat_history is not None:
            for message in chat_history["messages"]:
                message_history.append(
                    {
                        "userId": "1",
                        "sessionId": session_id,
                        "message": message["text"],
                        "isUser": message["sender"] == "user",
                        "timestamp": message["timestamp"],
                    }
                )
            return message_history

    def save_cabin_to_cart(
        self,
        user_id: ObjectId,
        cabin_item: CabinItem,
    ):
        new_item = cabin_item.model_dump(by_alias=True)

        updated_cart = self.db["carts"].find_one_and_update(
            {"user_id": ObjectId(user_id)},
            {
                "$push": {"items": new_item},
                "$set": {"updatedAt": datetime.now(timezone.utc)},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        out = {
            "cart_id": str(updated_cart["_id"]),
            "user_id": user_id,
        }
        new_item["_id"] = str(new_item["_id"])
        out = out | new_item

        return out

    def save_order(self, order: OrderIn):
        query = [
            {"$match": {"userId": ObjectId(order.userId)}},
            {
                "$project": {
                    "_id": 1,
                    "items": {
                        "$filter": {
                            "input": "$items",
                            "as": "item",
                            "cond": {
                                "$in": [
                                    "$$item._id",
                                    [ObjectId(_id) for _id in order.items],
                                ]
                            },
                        }
                    },
                }
            },
        ]
        cart = list(self.db["carts"].aggregate(query))
        order_dict = order.model_dump(by_alias=True)
        order_dict["items"] = cart[0]["items"]
        out = self.db["orders"].insert_one(order_dict)
        return out


if __name__ == "__main__":

    db_tool = DBTool()
    # item = CabinItem(
    #     cruiseId="6787675f9eced029e874720c",
    #     description="test",
    # )
    # res = db_tool.save_cabin_to_cart("67bc43923f9f1b182eb81908", item)
    # print(res)
    user_info = ContactInfo(
        title="Mr",
        firstName="hien",
        lastName="tran",
        email="hien@gmail.com",
        phone="0909090909",
    )
    order = OrderIn(
        userId="67bc43923f9f1b182eb8fbdc",
        contactInfo=user_info,
        totalAmount=1000000,
        items=["67e6251d2c346e6994cb782b"],
    )
    db_tool.save_order(order)
