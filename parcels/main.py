"""
FastAPI application for Parcel Management Service.
Implements 6 endpoints (no /route endpoint - that's Router service's responsibility).
"""

import hashlib
import uuid
from fastapi import FastAPI, HTTPException, Query
from typing import List

from models import (
    ParcelCreationInfo, DeliveryInfo, PickupInput,
    ParcelStatusHistory, HistoryEntry, ParcelList,
    TakeParcelInput, PutParcelInput
)
from domain import Item
from storage import registry
from services import ParcelService, RouterStubClient


# Initialize FastAPI app
app = FastAPI(
    title="Parcel Management Service",
    version="1.0.0",
    description="Microservice for managing parcel delivery lifecycle"
)

# Initialize services
router_client = RouterStubClient()
parcel_service = ParcelService(registry, router_client)


# Error response examples for documentation
ERROR_RESPONSES = {
    400: {
        "description": "Bad Request",
        "content": {
            "application/json": {
                "example": {"detail": "No valid route found for the given origin and destination"}
            }
        }
    },
    404: {
        "description": "Not Found",
        "content": {
            "application/json": {
                "example": {"detail": "Parcel not found"}
            }
        }
    }
}


@app.post(
    "/register",
    response_model=DeliveryInfo,
    status_code=200,
    responses={
        400: ERROR_RESPONSES[400]
    }
)
def register_parcel(parcel_info: ParcelCreationInfo):
    """
    Register a new parcel for delivery.

    Returns delivery cost, time, and pickup ID hash on success.

    **Error Responses:**
    - **400 Bad Request**: No valid route found for the given origin and destination
    """
    # Generate UUID and hash it
    pickup_uuid = str(uuid.uuid4())
    pickup_id_hash = hashlib.sha256(pickup_uuid.encode()).hexdigest()

    # Convert ItemInfo to Item domain objects
    items = [Item(name=item.name, value=item.value) for item in parcel_info.items]

    # Register parcel via service
    result = parcel_service.register_parcel(
        pickup_id_hash=pickup_id_hash,
        from_location=parcel_info.from_location,
        to_location=parcel_info.to_location,
        length=parcel_info.length,
        width=parcel_info.width,
        height=parcel_info.height,
        weight=parcel_info.weight,
        items=items
    )

    if result is None:
        raise HTTPException(
            status_code=400,
            detail="No valid route found for the given origin and destination"
        )

    cost, time = result

    return DeliveryInfo(
        cost=cost,
        time=time,
        pickupIdHash=pickup_id_hash
    )


@app.post(
    "/pickup",
    response_model=bool,
    status_code=200,
    responses={
        404: ERROR_RESPONSES[404]
    }
)
def pickup_parcel(pickup_input: PickupInput):
    """
    Record that a parcel has been picked up at its final destination.

    **Error Responses:**
    - **404 Not Found**: Parcel not found
    """
    success = parcel_service.pickup_parcel(pickup_input.pickupIdHash)

    if not success:
        raise HTTPException(status_code=404, detail="Parcel not found")

    return True


@app.get(
    "/track",
    response_model=ParcelStatusHistory,
    status_code=200,
    responses={
        404: ERROR_RESPONSES[404]
    }
)
def track_parcel(pickupIdHash: str = Query(..., description="Parcel identifier")):
    """
    Get tracking history and status for a parcel.

    **Error Responses:**
    - **404 Not Found**: Parcel not found
    """
    result = parcel_service.track_parcel(pickupIdHash)

    if result is None:
        raise HTTPException(status_code=404, detail="Parcel not found")

    total_stops, history_data = result

    # Convert to HistoryEntry models
    history_entries = [
        HistoryEntry(timestamp=ts, message=msg)
        for ts, msg in history_data
    ]

    return ParcelStatusHistory(
        totalStops=total_stops,
        history=history_entries
    )


@app.get("/parcels/{legId}", response_model=ParcelList, status_code=200)
def get_parcels_for_leg(legId: str):
    """
    Get list of parcels awaiting transport for a specific leg.
    Returns list of parcel IDs (pickup_id_hash values).
    """
    parcel_ids = parcel_service.get_parcels_for_leg(legId)

    return ParcelList(parcelIds=parcel_ids)


@app.post(
    "/take/{parcelId}",
    response_model=bool,
    status_code=200,
    responses={
        400: {
            "description": "Bad Request",
            "content": {
                "application/json": {
                    "example": {"detail": "Leg does not match the next expected leg for this parcel"}
                }
            }
        },
        404: ERROR_RESPONSES[404]
    }
)
def take_parcel(parcelId: str, take_input: TakeParcelInput):
    """
    Record that a parcel is departing on a specific leg.

    **Error Responses:**
    - **400 Bad Request**: Leg ID does not match the next expected leg for this parcel
    - **404 Not Found**: Parcel not found
    """
    result = parcel_service.record_departure(parcelId, take_input.legId)

    if result is None:
        raise HTTPException(status_code=404, detail="Parcel not found")

    if result is False:
        raise HTTPException(
            status_code=400,
            detail=f"Leg {take_input.legId} does not match the next expected leg for this parcel"
        )

    return True


@app.post(
    "/put/{parcelId}",
    response_model=bool,
    status_code=200,
    responses={
        404: ERROR_RESPONSES[404]
    }
)
def put_parcel(parcelId: str, put_input: PutParcelInput):
    """
    Record that a parcel has arrived at a location.

    **Error Responses:**
    - **404 Not Found**: Parcel not found
    """
    success = parcel_service.record_arrival(parcelId, put_input.location)

    if not success:
        raise HTTPException(status_code=404, detail="Parcel not found")

    return True


# Health check endpoint (bonus - not in spec but useful)
@app.get("/health", status_code=200)
def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy"}
