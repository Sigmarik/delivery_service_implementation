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

    The publicId is generated and hashed by the frontend before being sent to this service.

    Returns delivery cost and time on success.

    **Error Responses:**
    - **400 Bad Request**: No valid route found for the given origin and destination
    """
    # Convert ItemInfo to Item domain objects
    items = [Item(name=item.name, value=item.value) for item in parcel_info.items]

    # Register parcel via service using the provided publicId
    result = parcel_service.register_parcel(
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
    success = parcel_service.pickup_parcel(public_id)

    if not success:
        raise HTTPException(status_code=404, detail="Parcel not found")

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
    result = parcel_service.track_parcel(public_id)

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
    result = parcel_service.record_departure(parcelId, take_input.leg.id)

    if result is None:
        raise HTTPException(status_code=404, detail="Parcel not found")

    if result is False:
        raise HTTPException(
            status_code=400,
            detail=f"Leg {take_input.leg.id} does not match the next expected leg for this parcel"
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
