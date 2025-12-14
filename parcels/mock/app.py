"""
Mock Flask application for Parcel Management Service.
Implements the same endpoints as the FastAPI service but with simple mock responses.
"""

from flask import Flask, request, jsonify
import hashlib
import time

app = Flask(__name__)

# In-memory storage for mock parcels
parcels_db = {}
parcels_by_leg = {}


@app.route('/register', methods=['POST'])
def register_parcel():
    """
    Register a new parcel for delivery.
    Returns mock delivery cost and time.
    """
    data = request.get_json()

    # Validate required fields
    required_fields = ['publicId', 'from', 'to', 'length', 'width', 'height', 'weight', 'items']
    if not all(field in data for field in required_fields):
        return jsonify({"detail": "Missing required fields"}), 400

    # Store the parcel with mock data
    public_id = data['publicId']
    parcels_db[public_id] = {
        'from': data['from'],
        'to': data['to'],
        'dimensions': {
            'length': data['length'],
            'width': data['width'],
            'height': data['height'],
            'weight': data['weight']
        },
        'items': data['items'],
        'history': [
            {
                'timestamp': int(time.time()),
                'message': f"Parcel registered for delivery from {data['from']} to {data['to']}"
            }
        ],
        'current_leg_index': 0,
        'total_stops': 3  # Mock value
    }

    # Return mock cost and time
    return jsonify({
        "cost": 1500,  # Mock cost in cents
        "time": 7200   # Mock time in seconds (2 hours)
    }), 200


@app.route('/pickup', methods=['POST'])
def pickup_parcel():
    """
    Record that a parcel has been picked up at its final destination.
    """
    data = request.get_json()

    if 'privateParcelId' not in data:
        return jsonify({"detail": "Missing privateParcelId"}), 400

    # Hash the private ID to get the public ID
    public_id = hashlib.sha256(data['privateParcelId'].encode()).hexdigest()

    if public_id not in parcels_db:
        return jsonify({"detail": "Parcel not found"}), 404

    # Add pickup event to history
    parcels_db[public_id]['history'].append({
        'timestamp': int(time.time()),
        'message': "Parcel picked up by recipient"
    })

    return jsonify(True), 200


@app.route('/track', methods=['POST'])
def track_parcel():
    """
    Get tracking history and status for a parcel.
    """
    data = request.get_json()

    if 'privateParcelId' not in data:
        return jsonify({"detail": "Missing privateParcelId"}), 400

    # Hash the private ID to get the public ID
    public_id = hashlib.sha256(data['privateParcelId'].encode()).hexdigest()

    if public_id not in parcels_db:
        return jsonify({"detail": "Parcel not found"}), 404

    parcel = parcels_db[public_id]

    return jsonify({
        "totalStops": parcel['total_stops'],
        "history": parcel['history']
    }), 200


@app.route('/parcels/<leg_id>', methods=['GET'])
def get_parcels_for_leg(leg_id):
    """
    Get list of parcels awaiting transport for a specific leg.
    """
    parcel_ids = parcels_by_leg.get(leg_id, [])

    return jsonify({
        "parcelIds": parcel_ids
    }), 200


@app.route('/take/<parcel_id>', methods=['POST'])
def take_parcel(parcel_id):
    """
    Record that a parcel is departing on a specific leg.
    """
    data = request.get_json()

    if 'leg' not in data or 'id' not in data['leg']:
        return jsonify({"detail": "Missing leg id"}), 400

    if parcel_id not in parcels_db:
        return jsonify({"detail": "Parcel not found"}), 404

    leg_id = data['leg']['id']

    # Add departure event to history
    parcels_db[parcel_id]['history'].append({
        'timestamp': int(time.time()),
        'message': f"Parcel departed on leg {leg_id}"
    })

    # Remove from current leg's waiting list
    if leg_id in parcels_by_leg and parcel_id in parcels_by_leg[leg_id]:
        parcels_by_leg[leg_id].remove(parcel_id)

    return jsonify(True), 200


@app.route('/put/<parcel_id>', methods=['POST'])
def put_parcel(parcel_id):
    """
    Record that a parcel has arrived at a location.
    """
    data = request.get_json()

    if 'location' not in data:
        return jsonify({"detail": "Missing location"}), 400

    if parcel_id not in parcels_db:
        return jsonify({"detail": "Parcel not found"}), 404

    location = data['location']

    # Add arrival event to history
    parcels_db[parcel_id]['history'].append({
        'timestamp': int(time.time()),
        'message': f"Parcel arrived at {location}"
    })

    return jsonify(True), 200


@app.route('/clear', methods=['POST'])
def clear_db():
    global parcels_db
    global parcels_by_leg

    parcels_db = {}
    parcels_by_leg = {}
    return jsonify({}), 200


@app.route('/health', methods=['GET'])
def health_check():
    """
    Simple health check endpoint.
    """
    return jsonify({"status": "healthy"}), 200


# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({"detail": "Not found"}), 404


@app.errorhandler(400)
def bad_request(error):
    return jsonify({"detail": "Bad request"}), 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8001, debug=True)
