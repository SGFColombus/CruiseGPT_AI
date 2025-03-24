import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))
import os
from pymongo import MongoClient
import dotenv
from datetime import datetime
import re
from bson import ObjectId

from agent.tools.utils.utils import enrich_cruise
from pprint import pprint

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
                        "$elemMatch": {"status": "A"},
                        "$not": {
                            "$elemMatch": {
                                "fare": "P2P",
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
        cruises = list(self.collection.find(query).sort("sailStartDate", 1).limit(5))

        enriched_cruises = []
        for cruise in cruises:
            enriched_cruise = enrich_cruise(cruise, currency, country)
            enriched_cruises.append(enriched_cruise)
        return enriched_cruises


    def get_cruise_infor(self, cruise_id, currency: str = "USD", country: str = "US"):
        cruise = self.collection.find_one({"_id": ObjectId(cruise_id)})
        enriched_cruise = enrich_cruise(cruise, currency, country)
        return enriched_cruise

    
    def get_list_cabin(self, cruise_id, currency: str = "USD", country: str = "US"):
        pipeline = [
        # Match the specific cruise
        {"$match": {"_id": ObjectId(cruise_id)}},
        
        # Unwind the arrays to flatten the nested structure
        {"$unwind": "$prices"},
        {"$unwind": "$prices.suiteRates"},
        {"$unwind": "$prices.suiteRates.rates"},
        
        # Match the specific conditions
        {"$match": {
            "prices.currency": currency,
            "prices.countries": country,
            "prices.suiteRates.rates.status": "A",
            "prices.suiteRates.rates.fare": "P2P",
            "prices.suiteRates.rates.price": {"$ne": None}
        }},
        
        # Project only the fields we need
        {"$project": {
            "_id": 0,
            "cruise_id": {"$toString": "$_id"},
            "name": "$prices.suiteRates.name",
            "description": "$prices.suiteRates.description",
            "fare": "$prices.suiteRates.rates.fare",
            "price": "$prices.suiteRates.rates.price",
            "priceStatus": "$prices.suiteRates.rates.priceStatus",
            "originalPrice": "$prices.suiteRates.rates.originalPrice",
            "cabinUrl": "$prices.suiteRates.cabinUrl"
        }}
    ]
    
        return list(self.collection.aggregate(pipeline))

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


if __name__ == "__main__":
    import asyncio

    db_tool = DBTool()
    preferences = {
        # "departureAfter": None,
        # "departureBefore": "2025-12-31",
        # "destinations": ["Lisbon"],
        # "message": "Here are some cruises to Lisbon",
        "minPrice": 1000,
        "maxPrice": 100000,
        # "price_discount": False
    }

    pprint(
        asyncio.run(
            db_tool.get_list_cabin(
                cruise_id="6787671e9eced029e874702d",
                currency="AUD",
                country="AS",
            )
        )
    )
    # print(asyncio.run(db_tool.get_cruise_infor("DA250816C18")))
