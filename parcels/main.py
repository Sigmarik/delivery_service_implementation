"""
FastAPI application for Parcel Management Service.
Implements 6 endpoints (no /route endpoint - that's Router service's responsibility).
Matches the OpenAPI specification in context/openapi.yaml
"""

import hashlib
from fastapi import FastAPI, HTTPException
from typing import List

from models import (
    ParcelCreationInfo, DeliveryInfo, PickupInput, GetDeliveryStatusInput,
    ParcelStatusHistory, HistoryEntry, ParcelList,
    TakeParcelInput, PutParcelInput
)
from domain import Item
from storage import ParcelRegistry
from services import RouterStubClient


# Initialize FastAPI app
app = FastAPI(
    title="Parcel Management Service",
    version="1.0.0",
    description="Microservice for managing parcel delivery lifecycle"
)

# Initialize services
router_client = RouterStubClient()
registry = ParcelRegistry(router_client)


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

    The publicId is generated and hashed by the frontend before being sent to this service.

    Returns delivery cost and time on success.

    **Error Responses:**
    - **400 Bad Request**: No valid route found for the given origin and destination
    """
    # Convert ItemInfo to Item domain objects
    items = [Item(name=item.name, value=item.value) for item in parcel_info.items]

    # Register parcel via registry using the provided publicId
    result = registry.register_parcel(
        public_id=parcel_info.publicId,
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
        time=time
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

    The privateParcelId is the unhashed identifier. It will be hashed to look up the parcel.

    **Error Responses:**
    - **404 Not Found**: Parcel not found
    """
    # Hash the private ID to get the public ID for lookup
    public_id = hashlib.sha256(pickup_input.privateParcelId.encode()).hexdigest()
    parcel = registry.find_by_id(public_id)

    if parcel is None:
        raise HTTPException(status_code=404, detail="Parcel not found")

    parcel.history.pickup()
    return True


@app.post(
    "/track",
    response_model=ParcelStatusHistory,
    status_code=200,
    responses={
        404: ERROR_RESPONSES[404]
    }
)
def track_parcel(track_input: GetDeliveryStatusInput):
    """
    Get tracking history and status for a parcel.

    The privateParcelId is the unhashed identifier. It will be hashed to look up the parcel.

    Note: Changed to POST to properly support request body (OpenAPI spec shows GET but has requestBody).

    **Error Responses:**
    - **404 Not Found**: Parcel not found
    """
    # Hash the private ID to get the public ID for lookup
    public_id = hashlib.sha256(track_input.privateParcelId.encode()).hexdigest()
    parcel = registry.find_by_id(public_id)

    if parcel is None:
        raise HTTPException(status_code=404, detail="Parcel not found")

    # Convert events to human-readable messages using event.to_message()
    history_entries = [
        HistoryEntry(timestamp=event.timestamp, message=event.to_message())
        for event in parcel.history.events
    ]

    total_stops = len(parcel.route.leg_ids)

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
    parcel_ids = registry.get_parcels_for_leg(legId)

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
    parcel = registry.find_by_id(parcelId)

    if parcel is None:
        raise HTTPException(status_code=404, detail="Parcel not found")

    # Validate that leg_id matches the next expected leg
    expected_leg_id = registry.get_next_leg_id(parcel)
    if expected_leg_id != take_input.leg.id:
        raise HTTPException(
            status_code=400,
            detail=f"Leg {take_input.leg.id} does not match the next expected leg for this parcel"
        )

    parcel.history.departure(take_input.leg.id)
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
    parcel = registry.find_by_id(parcelId)

    if parcel is None:
        raise HTTPException(status_code=404, detail="Parcel not found")

    parcel.history.arrival(put_input.location)
    return True


# Health check endpoint (bonus - not in spec but useful)
@app.get("/health", status_code=200)
def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy"}
