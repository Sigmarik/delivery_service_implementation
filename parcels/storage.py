"""
In-memory storage for parcels.
Note: Not thread-safe. For production, add proper locking mechanisms.
"""

from typing import Optional, List
from domain import Parcel


class ParcelRegistry:
    """
    In-memory registry for parcels.
    Uses public_id (provided by frontend) as the index.
    """

    def __init__(self):
        self._parcels: dict[str, Parcel] = {}

    def register_parcel(self, parcel: Parcel) -> None:
        """Store a parcel by its public_id."""
        self._parcels[parcel.public_id] = parcel

    def find_by_id(self, public_id: str) -> Optional[Parcel]:
        """Find a parcel by its public_id."""
        return self._parcels.get(public_id)

    def get_all_parcels(self) -> List[Parcel]:
        """Return all registered parcels."""
        return list(self._parcels.values())


# Global singleton instance
registry = ParcelRegistry()
