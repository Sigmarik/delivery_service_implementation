"""
Integration tests for the Parcel Management Service API.
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from storage import registry


# Test client
client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_registry():
    """Clear in-memory storage between tests."""
    registry._parcels.clear()
    yield


def test_register_parcel_success():
    """Test successful parcel registration."""
    response = client.post("/register", json={
        "from": "CityA",
        "to": "CityB",
        "width": 10,
        "height": 10,
        "length": 20,
        "weight": 5.5,
        "items": [
            {"name": "Book", "value": 1000},
            {"name": "Laptop", "value": 50000}
        ]
    })

    assert response.status_code == 200
    data = response.json()
    assert "cost" in data
    assert "time" in data
    assert "pickupIdHash" in data
    assert data["cost"] > 0
    assert data["time"] > 0
    assert len(data["pickupIdHash"]) == 64  # SHA256 hash length


def test_register_parcel_no_route():
    """Test parcel registration with unknown locations (no route)."""
    response = client.post("/register", json={
        "from": "UnknownCity",
        "to": "AnotherUnknownCity",
        "width": 10,
        "height": 10,
        "length": 20,
        "weight": 5.5,
        "items": [{"name": "Item", "value": 1000}]
    })

    assert response.status_code == 400
    assert "No valid route" in response.json()["detail"]


def test_pickup_parcel():
    """Test pickup endpoint."""
    # First register a parcel
    reg_response = client.post("/register", json={
        "from": "CityA",
        "to": "CityB",
        "width": 10,
        "height": 10,
        "length": 20,
        "weight": 5.5,
        "items": [{"name": "Item", "value": 1000}]
    })
    pickup_id_hash = reg_response.json()["pickupIdHash"]

    # Pickup the parcel
    response = client.post("/pickup", json={
        "pickupIdHash": pickup_id_hash
    })

    assert response.status_code == 200
    assert response.json() is True


def test_pickup_parcel_not_found():
    """Test pickup with invalid parcel ID."""
    response = client.post("/pickup", json={
        "pickupIdHash": "invalid_hash"
    })

    assert response.status_code == 404


def test_track_parcel():
    """Test tracking endpoint after registration and pickup."""
    # Register parcel
    reg_response = client.post("/register", json={
        "from": "CityA",
        "to": "CityB",
        "width": 10,
        "height": 10,
        "length": 20,
        "weight": 5.5,
        "items": [{"name": "Item", "value": 1000}]
    })
    pickup_id_hash = reg_response.json()["pickupIdHash"]

    # Track initially (should be empty)
    track_response = client.get(f"/track?pickupIdHash={pickup_id_hash}")
    assert track_response.status_code == 200
    track_data = track_response.json()
    assert track_data["totalStops"] == 1
    assert len(track_data["history"]) == 0

    # Pickup parcel
    client.post("/pickup", json={"pickupIdHash": pickup_id_hash})

    # Track again (should have pickup event)
    track_response = client.get(f"/track?pickupIdHash={pickup_id_hash}")
    assert track_response.status_code == 200
    track_data = track_response.json()
    assert len(track_data["history"]) == 1
    assert "picked up" in track_data["history"][0]["message"].lower()


def test_track_not_found():
    """Test tracking with invalid parcel ID."""
    response = client.get("/track?pickupIdHash=invalid_hash")
    assert response.status_code == 404


def test_parcels_by_leg():
    """Test getting parcels awaiting transport for a specific leg."""
    # Register parcel from CityA to CityC (has 2 legs: leg-003, leg-004)
    reg_response = client.post("/register", json={
        "from": "CityA",
        "to": "CityC",
        "width": 10,
        "height": 10,
        "length": 20,
        "weight": 5.5,
        "items": [{"name": "Item", "value": 1000}]
    })
    pickup_id_hash = reg_response.json()["pickupIdHash"]

    # Check parcels for first leg (leg-003)
    response = client.get("/parcels/leg-003")
    assert response.status_code == 200
    data = response.json()
    assert pickup_id_hash in data["parcelIds"]

    # Check parcels for second leg (should be empty until departure on first leg)
    response = client.get("/parcels/leg-004")
    assert response.status_code == 200
    data = response.json()
    assert pickup_id_hash not in data["parcelIds"]


def test_take_and_put_parcel():
    """Test departure (take) and arrival (put) operations."""
    # Register parcel from CityA to CityC (2 legs)
    reg_response = client.post("/register", json={
        "from": "CityA",
        "to": "CityC",
        "width": 10,
        "height": 10,
        "length": 20,
        "weight": 5.5,
        "items": [{"name": "Item", "value": 1000}]
    })
    pickup_id_hash = reg_response.json()["pickupIdHash"]

    # Take parcel on first leg
    take_response = client.post(f"/take/{pickup_id_hash}", json={
        "legId": "leg-003"
    })
    assert take_response.status_code == 200
    assert take_response.json() is True

    # Put parcel at intermediate location
    put_response = client.post(f"/put/{pickup_id_hash}", json={
        "location": "IntermediateHub"
    })
    assert put_response.status_code == 200
    assert put_response.json() is True

    # Track to verify events
    track_response = client.get(f"/track?pickupIdHash={pickup_id_hash}")
    track_data = track_response.json()
    assert len(track_data["history"]) == 2
    assert "departed" in track_data["history"][0]["message"].lower()
    assert "arrived" in track_data["history"][1]["message"].lower()


def test_take_wrong_leg():
    """Test that take validates the leg ID."""
    # Register parcel
    reg_response = client.post("/register", json={
        "from": "CityA",
        "to": "CityC",
        "width": 10,
        "height": 10,
        "length": 20,
        "weight": 5.5,
        "items": [{"name": "Item", "value": 1000}]
    })
    pickup_id_hash = reg_response.json()["pickupIdHash"]

    # Try to take with wrong leg ID
    take_response = client.post(f"/take/{pickup_id_hash}", json={
        "legId": "leg-004"  # Should be leg-003 first
    })
    assert take_response.status_code == 400


def test_full_delivery_flow():
    """Test complete delivery flow from registration to final pickup."""
    # 1. Register parcel
    reg_response = client.post("/register", json={
        "from": "CityA",
        "to": "CityB",
        "width": 10,
        "height": 10,
        "length": 20,
        "weight": 5.5,
        "items": [{"name": "Item", "value": 1000}]
    })
    assert reg_response.status_code == 200
    pickup_id_hash = reg_response.json()["pickupIdHash"]

    # 2. Take parcel on first (only) leg
    take_response = client.post(f"/take/{pickup_id_hash}", json={
        "legId": "leg-001"
    })
    assert take_response.status_code == 200

    # 3. Put parcel at final destination
    put_response = client.post(f"/put/{pickup_id_hash}", json={
        "location": "CityB"
    })
    assert put_response.status_code == 200

    # 4. Pickup parcel at destination
    pickup_response = client.post("/pickup", json={
        "pickupIdHash": pickup_id_hash
    })
    assert pickup_response.status_code == 200

    # 5. Track to verify complete history
    track_response = client.get(f"/track?pickupIdHash={pickup_id_hash}")
    track_data = track_response.json()
    assert len(track_data["history"]) == 3
    assert track_data["totalStops"] == 1


def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
