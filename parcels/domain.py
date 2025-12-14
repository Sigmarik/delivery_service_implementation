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
    length: int
    width: int
    height: int
    weight: int
    items: List[Item]
    route: Route
    history: ParcelHistory

    def get_next_leg_id(self) -> str | None:
        """
        Determine the next expected leg based on history.
        Returns None if parcel is in transit or has completed all legs.
        """
        print(f"Getting on of legs {self.route.leg_ids}")
        # If last event is a departure, parcel is currently in transit
        if self.history.events and isinstance(self.history.events[-1], DepartureEvent):
            print(f"Parcel is in transit")
            return None

        # Count departure events to determine current leg index
        departure_count = sum(
            1 for event in self.history.events
            if isinstance(event, DepartureEvent)
        )
        print(f"Parcel departed {departure_count} times")

        # Check if all legs have been completed
        if departure_count >= len(self.route.leg_ids):
            print(f"Parcel arrived at destination")
            return None
        print(f"Parcel is ready to travel via {self.route.leg_ids[departure_count]}")
        return self.route.leg_ids[departure_count]
