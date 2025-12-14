# Parcel Management Microservice

A FastAPI-based microservice prototype for managing parcel delivery lifecycle. This service handles parcel registration, tracking, and event management for a delivery system.

## Features

- **Parcel Registration**: Register parcels with dimensions, weight, and items
- **Route Management**: Integrates with Router service (stubbed for prototype)
- **Event Tracking**: Track parcel lifecycle through departure, arrival, and pickup events
- **In-Memory Storage**: Simple in-memory database for prototype
- **RESTful API**: 6 endpoints for parcel operations

## Architecture

The service follows a clean architecture with clear separation of concerns:

- **domain.py**: Data-only domain entities (Parcel, Route, Events)
- **storage.py**: Parcel registry with business logic (ParcelRegistry)
- **services.py**: Router stub client (RouterStubClient)
- **models.py**: Pydantic models for API validation
- **main.py**: FastAPI application with endpoints
- **test_api.py**: Integration tests

## Setup

### Prerequisites

- Python 3.8+
- pip

### Installation

1. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Service

Start the server:
```bash
uvicorn main:app --reload --port 8000
```

The service will be available at:
- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- Alternative docs: http://localhost:8000/redoc

## API Endpoints

### 1. POST /register
Register a new parcel for delivery.

**Request:**
```json
{
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
}
```

**Response (200):**
```json
{
  "cost": 655,
  "time": 60,
  "pickupIdHash": "a1b2c3d4..."
}
```

**Error (400):** No route found for given locations

### 2. POST /pickup
Record that a parcel has been picked up at final destination.

**Request:**
```json
{
  "pickupIdHash": "a1b2c3d4..."
}
```

**Response (200):** `true`

**Error (404):** Parcel not found

### 3. GET /track
Get parcel tracking history and status.

**Query Parameters:**
- `pickupIdHash`: Parcel identifier

**Response (200):**
```json
{
  "totalStops": 1,
  "history": [
    {
      "timestamp": 1702345678,
      "message": "Departed on leg leg-001"
    },
    {
      "timestamp": 1702349278,
      "message": "Arrived at CityB"
    }
  ]
}
```

**Error (404):** Parcel not found

### 4. GET /parcels/{legId}
Get parcels awaiting transport for a specific leg.

**Response (200):**
```json
{
  "parcelIds": ["a1b2c3d4...", "e5f6g7h8..."]
}
```

### 5. POST /take/{parcelId}
Record that a parcel is departing on a specific leg.

**Request:**
```json
{
  "legId": "leg-001"
}
```

**Response (200):** `true`

**Error (404):** Parcel not found
**Error (400):** Leg ID doesn't match next expected leg

### 6. POST /put/{parcelId}
Record that a parcel has arrived at a location.

**Request:**
```json
{
  "location": "CityB"
}
```

**Response (200):** `true`

**Error (404):** Parcel not found

## Testing

Run integration tests:
```bash
pytest test_api.py -v
```

All tests should pass:
```
11 passed in 0.38s
```

## Design Decisions

### Single Identifier
The `pickup_id_hash` serves as both public and private identifier. It's a SHA256 hash of a randomly generated UUID4.

### Data-Only Domain
Domain entities (Parcel, Route, etc.) contain no business logic. All operations are in the ParcelRegistry layer.

### Derived State
Parcel state is derived from event history rather than stored explicitly. The last event type determines the current state.

### Opaque Leg IDs
The service treats leg IDs as opaque strings. The Router service owns the Leg/LegType details.

### Router Stub
For prototype development, a stub Router client returns predefined routes for common city pairs:
- CityA ↔ CityB (1 leg)
- CityA ↔ CityC (2 legs)
- CityB ↔ CityC (1 leg)
- CityA ↔ CityD (3 legs)
- NewYork ↔ London (1 leg)

Unknown routes return a 400 error.

## Project Structure

```
parcels/
├── venv/                # Virtual environment
├── domain.py            # Domain entities
├── storage.py           # In-memory storage
├── services.py          # Business logic
├── models.py            # API models
├── main.py              # FastAPI app
├── test_api.py          # Integration tests
├── requirements.txt     # Dependencies
└── README.md            # This file
```

## Limitations (Prototype)

- **In-memory storage**: Data is lost on restart (no persistence)
- **Not thread-safe**: Single-threaded only
- **No authentication**: Open API endpoints
- **Limited routes**: Only predefined city pairs work
- **No containerization**: Direct Python execution
- **Stub router**: Mock Router service for development

## Future Enhancements

For production deployment, consider:
- Persistent database (PostgreSQL, MongoDB)
- Thread-safe storage with proper locking
- Authentication and authorization
- Integration with real Router service
- Docker containerization
- Logging and monitoring
- Rate limiting
- Input validation enhancements
- API versioning

## License

MIT
