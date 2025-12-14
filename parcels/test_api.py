"""
Integration tests for the Parcel Management Service API.
"""

import pytest
import hashlib
import uuid
from fastapi.testclient import TestClient
from main import app, registry


# Test client
client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_registry():
    """Clear in-memory storage between tests."""
    registry._parcels.clear()
    yield


def generate_parcel_id():
    """Generate a UUID and its hash for testing."""
    private_id = str(uuid.uuid4())
    public_id = hashlib.sha256(private_id.encode()).hexdigest()
    return private_id, public_id


def test_register_parcel_success():
    """Test successful parcel registration."""
    private_id, public_id = generate_parcel_id()

    response = client.post("/register", json={
        "from": "CityA",
        "to": "CityB",
        "publicId": public_id,
        "width": 10,
        "height": 10,
        "length": 20,
        "weight": 5,
        "items": [
            {"name": "Book", "value": 1000},
            {"name": "Laptop", "value": 50000}
        ]
    })

    assert response.status_code == 200
    data = response.json()
    assert "cost" in data
    assert "time" in data
    assert "pickupIdHash" not in data  # Should not return the hash
    assert data["cost"] > 0
    assert data["time"] > 0


def test_register_parcel_no_route():
    """Test parcel registration with unknown locations (no route)."""
    private_id, public_id = generate_parcel_id()

    response = client.post("/register", json={
        "from": "UnknownCity",
        "to": "AnotherUnknownCity",
        "publicId": public_id,
        "width": 10,
        "height": 10,
        "length": 20,
        "weight": 5,
        "items": [{"name": "Item", "value": 1000}]
    })

    assert response.status_code == 400
    assert "No valid route" in response.json()["detail"]


def test_pickup_parcel():
    """Test pickup endpoint."""
    private_id, public_id = generate_parcel_id()

    # First register a parcel
    reg_response = client.post("/register", json={
        "from": "CityA",
        "to": "CityB",
        "publicId": public_id,
        "width": 10,
        "height": 10,
        "length": 20,
        "weight": 5,
        "items": [{"name": "Item", "value": 1000}]
    })
    assert reg_response.status_code == 200

    # Pickup the parcel using private (unhashed) ID
    response = client.post("/pickup", json={
        "privateParcelId": private_id
    })

    assert response.status_code == 200
    assert response.json() is True


def test_pickup_parcel_not_found():
    """Test pickup with invalid parcel ID."""
    response = client.post("/pickup", json={
        "privateParcelId": "invalid_id"
    })

    assert response.status_code == 404


def test_track_parcel():
    """Test tracking endpoint after registration and pickup."""
    private_id, public_id = generate_parcel_id()

    # Register parcel
    reg_response = client.post("/register", json={
        "from": "CityA",
        "to": "CityB",
        "publicId": public_id,
        "width": 10,
        "height": 10,
        "length": 20,
        "weight": 5,
        "items": [{"name": "Item", "value": 1000}]
    })
    assert reg_response.status_code == 200

    # Track initially (should be empty)
    track_response = client.post("/track", json={"privateParcelId": private_id})
    assert track_response.status_code == 200
    track_data = track_response.json()
    assert track_data["totalStops"] == 1
    assert len(track_data["history"]) == 0

    # Pickup parcel
    client.post("/pickup", json={"privateParcelId": private_id})

    # Track again (should have pickup event)
    track_response = client.post("/track", json={"privateParcelId": private_id})
    assert track_response.status_code == 200
    track_data = track_response.json()
    assert len(track_data["history"]) == 1
    assert "picked up" in track_data["history"][0]["message"].lower()


def test_track_not_found():
    """Test tracking with invalid parcel ID."""
    response = client.post("/track", json={"privateParcelId": "invalid_id"})
    assert response.status_code == 404


def test_parcels_by_leg():
    """Test getting parcels awaiting transport for a specific leg."""
    private_id, public_id = generate_parcel_id()

    # Register parcel from CityA to CityC (has 2 legs: leg-003, leg-004)
    reg_response = client.post("/register", json={
        "from": "CityA",
        "to": "CityC",
        "publicId": public_id,
        "width": 10,
        "height": 10,
        "length": 20,
        "weight": 5,
        "items": [{"name": "Item", "value": 1000}]
    })
    assert reg_response.status_code == 200

    # Check parcels for first leg (leg-003)
    response = client.get("/parcels/leg-003")
    assert response.status_code == 200
    data = response.json()
    assert public_id in data["parcelIds"]

    # Check parcels for second leg (should be empty until departure on first leg)
    response = client.get("/parcels/leg-004")
    assert response.status_code == 200
    data = response.json()
    assert public_id not in data["parcelIds"]


def test_take_and_put_parcel():
    """Test departure (take) and arrival (put) operations."""
    private_id, public_id = generate_parcel_id()

    # Register parcel from CityA to CityC (2 legs)
    reg_response = client.post("/register", json={
        "from": "CityA",
        "to": "CityC",
        "publicId": public_id,
        "width": 10,
        "height": 10,
        "length": 20,
        "weight": 5,
        "items": [{"name": "Item", "value": 1000}]
    })
    assert reg_response.status_code == 200

    # Take parcel on first leg (using public ID in path)
    take_response = client.post(f"/take/{public_id}", json={
        "leg": {"id": "leg-003"}
    })
    assert take_response.status_code == 200
    assert take_response.json() is True

    # Put parcel at intermediate location
    put_response = client.post(f"/put/{public_id}", json={
        "location": "IntermediateHub"
    })
    assert put_response.status_code == 200
    assert put_response.json() is True

    # Track to verify events
    track_response = client.post("/track", json={"privateParcelId": private_id})
    track_data = track_response.json()
    assert len(track_data["history"]) == 2
    assert "departed" in track_data["history"][0]["message"].lower()
    assert "arrived" in track_data["history"][1]["message"].lower()


def test_take_wrong_leg():
    """Test that take validates the leg ID."""
    private_id, public_id = generate_parcel_id()

    # Register parcel
    reg_response = client.post("/register", json={
        "from": "CityA",
        "to": "CityC",
        "publicId": public_id,
        "width": 10,
        "height": 10,
        "length": 20,
        "weight": 5,
        "items": [{"name": "Item", "value": 1000}]
    })
    assert reg_response.status_code == 200

    # Try to take with wrong leg ID
    take_response = client.post(f"/take/{public_id}", json={
        "leg": {"id": "leg-004"}  # Should be leg-003 first
    })
    assert take_response.status_code == 400


def test_full_delivery_flow():
    """Test complete delivery flow from registration to final pickup."""
    private_id, public_id = generate_parcel_id()

    # 1. Register parcel
    reg_response = client.post("/register", json={
        "from": "CityA",
        "to": "CityB",
        "publicId": public_id,
        "width": 10,
        "height": 10,
        "length": 20,
        "weight": 5,
        "items": [{"name": "Item", "value": 1000}]
    })
    assert reg_response.status_code == 200

    # 2. Take parcel on first (only) leg
    take_response = client.post(f"/take/{public_id}", json={
        "leg": {"id": "leg-001"}
    })
    assert take_response.status_code == 200

    # 3. Put parcel at final destination
    put_response = client.post(f"/put/{public_id}", json={
        "location": "CityB"
    })
    assert put_response.status_code == 200

    # 4. Pickup parcel at destination
    pickup_response = client.post("/pickup", json={
        "privateParcelId": private_id
    })
    assert pickup_response.status_code == 200

    # 5. Track to verify complete history
    track_response = client.post("/track", json={"privateParcelId": private_id})
    track_data = track_response.json()
    assert len(track_data["history"]) == 3
    assert track_data["totalStops"] == 1


def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
