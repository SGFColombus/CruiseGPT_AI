from pydantic import BaseModel
from datetime import datetime, timezone
from typing import List, Optional, Literal
from bson import ObjectId
from .cabin_item import CabinItem


from typing import Any


class ContactInfo(BaseModel):
    title: str
    firstName: str
    lastName: str
    email: str
    phone: str


class OrderIn(BaseModel):
    userId: str

    contactInfo: ContactInfo
    shippingAddress: str | None = None
    billingAddress: str | None = None
    items: List[str] | None = None
    totalAmount: int
    status: Literal["pending", "paid", "failed", "cancelled", "refunded"] | None = None
    paymentMethod: (
        Literal["stripe", "paypal", "momo", "zalo", "bank_transfer"] | None
    ) = None
    transactionId: str | None = None
