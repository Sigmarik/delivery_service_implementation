"""
In-memory storage for parcels with business logic.
Note: Not thread-safe. For production, add proper locking mechanisms.
"""

from typing import Optional, List, Tuple
from domain import Parcel, ParcelHistory, Item


class ParcelRegistry:
    """
    In-memory registry for parcels with business logic.
    Uses public_id (provided by frontend) as the index.
    """

    def __init__(self, router_client):
        self._parcels: dict[str, Parcel] = {}
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
            length=length,
            width=width,
            height=height,
            weight=weight,
            items=items,
            route=route,
            history=ParcelHistory()
        )
        parcel.history.arrival(from_location)
        print(f"Legs are {route.leg_ids}")

        # Store parcel
        self._parcels[parcel.public_id] = parcel

        return (route.cost, route.time)

    def find_by_id(self, public_id: str) -> Optional[Parcel]:
        """Find a parcel by its public_id."""
        return self._parcels.get(public_id)

    def get_parcels_for_leg(self, leg_id: str) -> List[str]:
        """
        Get list of parcel IDs awaiting transport for a specific leg.
        Returns list of public IDs.
        """
        result = []
        for parcel in self._parcels.values():
            next_leg_id = parcel.get_next_leg_id()
            if next_leg_id == leg_id:
                result.append(parcel.public_id)

        return result
