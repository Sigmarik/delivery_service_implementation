"""
Business logic layer for parcel management.
Contains ParcelService for business operations and RouterStubClient for mock routing.
"""

import time
from typing import Optional, List, Tuple
from domain import (
    Parcel, Route, ParcelHistory, ParcelEvent,
    PickupEvent, ArrivalEvent, DepartureEvent, Item
)
from storage import ParcelRegistry


class RouterStubClient:
    """
    Mock Router service for development.
    Returns predefined routes with opaque leg IDs.
    """

    def __init__(self):
        self._routes = self._create_predefined_routes()

    def get_route(self, from_loc: str, to_loc: str, weight: int, value: int) -> Optional[Route]:
        """
        Get a route between two locations.
        Returns None if no route exists (simulates routing failure).
        """
        route_key = (from_loc.lower(), to_loc.lower())
        base_route = self._routes.get(route_key)

        if base_route is None:
            return None

        # Calculate cost based on weight and value
        cost = self._calculate_cost(base_route.cost, weight, value)

        # Return route with calculated cost
        return Route(
            leg_ids=base_route.leg_ids.copy(),
            cost=cost,
            time=base_route.time
        )

    def _calculate_cost(self, base_cost: int, weight: int, value: int) -> int:
        """Calculate total cost based on base cost, weight, and value."""
        return int(base_cost + (weight * 10) + (value * 0.01))

    def _create_predefined_routes(self) -> dict[Tuple[str, str], Route]:
        """Create predefined routes between common locations."""
        return {
            ("citya", "cityb"): Route(leg_ids=["leg-001"], cost=100, time=60),
            ("cityb", "citya"): Route(leg_ids=["leg-002"], cost=100, time=60),
            ("citya", "cityc"): Route(leg_ids=["leg-003", "leg-004"], cost=200, time=120),
            ("cityc", "citya"): Route(leg_ids=["leg-005", "leg-006"], cost=200, time=120),
            ("cityb", "cityc"): Route(leg_ids=["leg-007"], cost=150, time=90),
            ("cityc", "cityb"): Route(leg_ids=["leg-008"], cost=150, time=90),
            ("citya", "cityd"): Route(leg_ids=["leg-009", "leg-010", "leg-011"], cost=300, time=180),
            ("cityd", "citya"): Route(leg_ids=["leg-012", "leg-013", "leg-014"], cost=300, time=180),
            ("newyork", "london"): Route(leg_ids=["leg-015"], cost=500, time=420),
            ("london", "newyork"): Route(leg_ids=["leg-016"], cost=500, time=420),
        }


class ParcelService:
    """
    Service layer containing all business logic for parcel management.
    """

    def __init__(self, registry: ParcelRegistry, router_client: RouterStubClient):
        self.registry = registry
        self.router = router_client

    def register_parcel(
        self,
        public_id: str,
        from_location: str,
        to_location: str,
        length: int,
        width: int,
        height: int,
        weight: int,
        items: List[Item]
    ) -> Optional[Tuple[int, int]]:
        """
        Register a new parcel.
        Returns (cost, time) tuple if successful, None if no route found.
        """
        # Calculate total value
        total_value = sum(item.value for item in items)

        # Get route from router service
        route = self.router.get_route(from_location, to_location, weight, total_value)
        if route is None:
            return None

        # Create parcel with empty history
        parcel = Parcel(
            public_id=public_id,
            from_location=from_location,
            to_location=to_location,
            length=length,
            width=width,
            height=height,
            weight=weight,
            items=items,
            route=route,
            history=ParcelHistory()
        )

        # Register parcel
        self.registry.register_parcel(parcel)

        return (route.cost, route.time)

    def pickup_parcel(self, private_parcel_id: str) -> bool:
        """
        Record pickup event for a parcel.
        Returns True if successful, False if parcel not found.
        """
        parcel = self.registry.find_by_id(private_parcel_id)
        if parcel is None:
            return False

        # Add pickup event
        event = PickupEvent(timestamp=int(time.time()))
        parcel.history.events.append(event)

        return True

    def track_parcel(self, private_parcel_id: str) -> Optional[Tuple[int, List[Tuple[int, str]]]]:
        """
        Get parcel tracking information.
        Returns (total_stops, history_entries) where history_entries is list of (timestamp, message).
        Returns None if parcel not found.
        """
        parcel = self.registry.find_by_id(private_parcel_id)
        if parcel is None:
            return None

        # Convert events to human-readable messages
        history_entries = []
        for event in parcel.history.events:
            message = self._event_to_message(event)
            history_entries.append((event.timestamp, message))

        total_stops = len(parcel.route.leg_ids)

        return (total_stops, history_entries)

    def get_parcels_for_leg(self, leg_id: str) -> List[str]:
        """
        Get list of parcel IDs awaiting transport for a specific leg.
        Returns list of public IDs.
        """
        result = []
        for parcel in self.registry.get_all_parcels():
            next_leg_id = self._get_next_leg_id(parcel)
            if next_leg_id == leg_id:
                result.append(parcel.public_id)

        return result

    def record_departure(self, parcel_id: str, leg_id: str) -> Optional[bool]:
        """
        Record departure event for a parcel on a specific leg.
        Returns True if successful, None if parcel not found, False if leg validation fails.
        """
        parcel = self.registry.find_by_id(parcel_id)
        if parcel is None:
            return None

        # Validate that leg_id matches the next expected leg
        expected_leg_id = self._get_next_leg_id(parcel)
        if expected_leg_id != leg_id:
            return False

        # Add departure event
        event = DepartureEvent(timestamp=int(time.time()), leg_id=leg_id)
        parcel.history.events.append(event)

        return True

    def record_arrival(self, parcel_id: str, location: str) -> bool:
        """
        Record arrival event for a parcel at a location.
        Returns True if successful, False if parcel not found.
        """
        parcel = self.registry.find_by_id(parcel_id)
        if parcel is None:
            return False

        # Add arrival event
        event = ArrivalEvent(timestamp=int(time.time()), to=location)
        parcel.history.events.append(event)

        return True

    def _get_next_leg_id(self, parcel: Parcel) -> Optional[str]:
        """
        Determine the next expected leg for a parcel based on its history.
        Returns None if parcel has completed all legs.
        """
        # Count departure events to determine current leg index
        departure_count = sum(
            1 for event in parcel.history.events
            if isinstance(event, DepartureEvent)
        )

        # Check if all legs have been completed
        if departure_count >= len(parcel.route.leg_ids):
            return None

        return parcel.route.leg_ids[departure_count]

    def _event_to_message(self, event: ParcelEvent) -> str:
        """Convert a parcel event to a human-readable message."""
        if isinstance(event, PickupEvent):
            return "Parcel picked up at final destination"
        elif isinstance(event, ArrivalEvent):
            return f"Arrived at {event.to}"
        elif isinstance(event, DepartureEvent):
            return f"Departed on leg {event.leg_id}"
        else:
            return "Unknown event"

    def _derive_state_from_history(self, history: ParcelHistory) -> str:
        """
        Derive parcel state from its event history.
        Returns one of: 'registered', 'in_transit', 'delivered', 'picked_up'
        """
        if not history.events:
            return "registered"

        last_event = history.events[-1]

        if isinstance(last_event, PickupEvent):
            return "picked_up"
        elif isinstance(last_event, ArrivalEvent):
            return "delivered"
        elif isinstance(last_event, DepartureEvent):
            return "in_transit"
        else:
            return "registered"
