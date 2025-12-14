"""
In-memory storage for parcels.
Note: Not thread-safe. For production, add proper locking mechanisms.
"""

from typing import Optional, List
from domain import Parcel


class ParcelRegistry:
    """
    In-memory registry for parcels.
    Uses pickup_id_hash as the single index (serves as both public and private identifier).
    """

    def __init__(self):
        self._parcels: dict[str, Parcel] = {}

    def register_parcel(self, parcel: Parcel) -> None:
        """Store a parcel by its pickup_id_hash."""
        self._parcels[parcel.pickup_id_hash] = parcel

    def find_by_id(self, pickup_id_hash: str) -> Optional[Parcel]:
        """Find a parcel by its pickup_id_hash."""
        return self._parcels.get(pickup_id_hash)

    def get_all_parcels(self) -> List[Parcel]:
        """Return all registered parcels."""
        return list(self._parcels.values())


# Global singleton instance
registry = ParcelRegistry()
