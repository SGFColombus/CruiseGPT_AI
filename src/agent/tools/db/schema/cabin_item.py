from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import List, Optional
from bson import ObjectId


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if ObjectId.is_valid(v):
            return ObjectId(v)
        raise ValueError("Invalid ObjectId")


class CabinItem(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    cruiseId: str
    description: str
    currency: str = "USD"
    country: str = "US"
    quantity: int = 1

    class Config:
        json_encoders = {PyObjectId: str}
        arbitrary_types_allowed = True
