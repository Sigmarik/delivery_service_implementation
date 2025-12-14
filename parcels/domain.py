"""
Domain entities for the Parcel Management Service.
"""

import time
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

    def to_message(self) -> str:
        """Convert event to human-readable message."""
        raise NotImplementedError("Subclasses must implement to_message()")


@dataclass(frozen=True)
class PickupEvent(ParcelEvent):
    """Event recorded when parcel is picked up at final destination."""

    def to_message(self) -> str:
        """Convert event to human-readable message."""
        return "Parcel picked up at final destination"


@dataclass(frozen=True)
class ArrivalEvent(ParcelEvent):
    """Event recorded when parcel arrives at a location."""
    to: str  # Arrival location

    def to_message(self) -> str:
        """Convert event to human-readable message."""
        return f"Arrived at {self.to}"


@dataclass(frozen=True)
class DepartureEvent(ParcelEvent):
    """Event recorded when parcel departs on a leg."""
    leg_id: str  # Opaque leg identifier

    def to_message(self) -> str:
        """Convert event to human-readable message."""
        return f"Departed on leg {self.leg_id}"


@dataclass
class ParcelHistory:
    """Maintains ordered list of events for a parcel."""
    events: List[ParcelEvent] = field(default_factory=list)

    def departure(self, leg_id: str) -> None:
        """Record a departure event for a specific leg."""
        event = DepartureEvent(timestamp=int(time.time()), leg_id=leg_id)
        self.events.append(event)

    def arrival(self, location: str) -> None:
        """Record an arrival event at a location."""
        event = ArrivalEvent(timestamp=int(time.time()), to=location)
        self.events.append(event)

    def pickup(self) -> None:
        """Record a pickup event at final destination."""
        event = PickupEvent(timestamp=int(time.time()))
        self.events.append(event)


@dataclass
class Parcel:
    """
    Represents a parcel in the delivery system.
    State is derived from history, not stored explicitly.
    """
    public_id: str  # Public identifier (hash) provided by frontend
    from_location: str
    to_location: str
    length: int
    width: int
    height: int
    weight: int
    items: List[Item]
    route: Route
    history: ParcelHistory
