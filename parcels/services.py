"""
Router client for parcel management.
Contains RouterClient for real routing and RouterStubClient for mock routing.
"""

import requests
from typing import Optional, Tuple
from domain import Route


class RouterClient:
    """
    Real Router service client.
    Communicates with Router service via HTTP on localhost:5000.
    """

    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url

    def get_route(self, from_loc: str, to_loc: str, weight: int, value: int) -> Optional[Route]:
        """
        Get a route between two locations from Router service.
        Returns None if no route exists or if service is unavailable.
        """
        try:
            response = requests.post(
                f"{self.base_url}/route",
                json={
                    "from": from_loc,
                    "to": to_loc,
                    "weight": weight,
                    "value": value
                },
                timeout=5
            )

            if response.status_code == 400:
                # No route found
                return None

            response.raise_for_status()
            data = response.json()

            return Route(
                leg_ids=data["legs"],
                cost=data["cost"],
                time=data["time"]
            )

        except requests.exceptions.RequestException:
            # Service unavailable or network error
            return None
        except (KeyError, ValueError):
            # Invalid response format
            return None


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
