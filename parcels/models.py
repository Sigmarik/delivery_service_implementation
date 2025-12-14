"""
Pydantic models for API request and response validation.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List


class ItemInfo(BaseModel):
    """Item information in a parcel."""
    name: str
    value: int


class ParcelCreationInfo(BaseModel):
    """Request model for parcel registration."""
    model_config = ConfigDict(populate_by_name=True)

    items: List[ItemInfo] = Field(alias="items")
    length: int
    width: int
    height: int
    weight: float

    # Use Field with alias to match the exact field names from OpenAPI spec
    from_location: str = Field(alias="from")
    to_location: str = Field(alias="to")


class DeliveryInfo(BaseModel):
    """Response model for successful parcel registration."""
    cost: int
    time: int
    pickupIdHash: str


class PickupInput(BaseModel):
    """Request model for pickup endpoint."""
    pickupIdHash: str


class HistoryEntry(BaseModel):
    """Single history entry in parcel tracking."""
    timestamp: int
    message: str


class ParcelStatusHistory(BaseModel):
    """Response model for parcel tracking."""
    totalStops: int
    history: List[HistoryEntry]


class ParcelList(BaseModel):
    """Response model for parcels by leg endpoint."""
    parcelIds: List[str]


class TakeParcelInput(BaseModel):
    """Request model for take (departure) endpoint."""
    legId: str


class PutParcelInput(BaseModel):
    """Request model for put (arrival) endpoint."""
    location: str
