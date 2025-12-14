"""
Domain entities for the Parcel Management Service.
All classes are data-only with no business logic methods.
"""

from dataclasses import dataclass, field
from abc import ABC
from typing import List


@dataclass(frozen=True)
class Item:
    """Represents an item in a parcel."""
    name: str
    value: int


@dataclass
class Route:
    """Represents a delivery route with pre-calculated cost and time."""
    leg_ids: List[str]  # Opaque leg identifiers from Router service
    cost: int  # Total cost from Router
    time: int  # Total time from Router


@dataclass(frozen=True)
class ParcelEvent(ABC):
    """Base class for parcel events."""
    timestamp: int  # Unix epoch timestamp


@dataclass(frozen=True)
class PickupEvent(ParcelEvent):
    """Event recorded when parcel is picked up at final destination."""
    pass


@dataclass(frozen=True)
class ArrivalEvent(ParcelEvent):
    """Event recorded when parcel arrives at a location."""
    to: str  # Arrival location


@dataclass(frozen=True)
class DepartureEvent(ParcelEvent):
    """Event recorded when parcel departs on a leg."""
    leg_id: str  # Opaque leg identifier


@dataclass
class ParcelHistory:
    """Maintains ordered list of events for a parcel."""
    events: List[ParcelEvent] = field(default_factory=list)


@dataclass
class Parcel:
    """
    Represents a parcel in the delivery system.
    State is derived from history, not stored explicitly.
    """
    pickup_id_hash: str  # SHA256 hash of UUID - serves as both public and private ID
    from_location: str
    to_location: str
    length: int
    width: int
    height: int
    weight: float
    items: List[Item]
    route: Route
    history: ParcelHistory
