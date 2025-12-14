from flask import Flask, request, jsonify
from flask_cors import CORS
import json
from typing import Dict, Any, Optional, List
import heapq

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# ============================================
# Data Models (based on OpenAPI schema)
# ============================================

class LegId:
    """Identifier for a delivery leg"""
    def __init__(self, id: str):
        self.id = id
    
    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id}

class Leg:
    """Represents a transportation leg between locations"""
    def __init__(self, id: str, operator: str, from_location: str, to_location: str, 
                 max_weight: float, time: int, base_cost: float = 0, 
                 weight_factor: float = 0.5, value_factor: float = 0.01):
        self.id = id
        self.operator = operator
        self.from_location = from_location
        self.to_location = to_location
        self.max_weight = max_weight
        self.time = time
        self.base_cost = base_cost
        self.weight_factor = weight_factor
        self.value_factor = value_factor
    
    def cost(self, parcel_weight: float, parcel_value: int) -> float:
        """Calculate the cost for this leg based on parcel weight and value"""
        if parcel_weight > self.max_weight:
            return float('inf')  # Can't use this leg if parcel is too heavy
        
        return (self.base_cost + 
                self.weight_factor * parcel_weight + 
                self.value_factor * parcel_value)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "operator": self.operator,
            "from": self.from_location,
            "to": self.to_location,
            "maxWeight": self.max_weight,
            "time": self.time,
            "base_cost": self.base_cost,
            "weight_factor": self.weight_factor,
            "value_factor": self.value_factor
        }

class ParcelDescription:
    """Description of a parcel for routing purposes"""
    def __init__(self, from_location: str, to_location: str, weight: float, value: int):
        self.from_location = from_location
        self.to_location = to_location
        self.weight = weight
        self.value = value
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ParcelDescription':
        return cls(
            from_location=data['from'],
            to_location=data['to'],
            weight=float(data['weight']),
            value=int(data['value'])
        )

class LegList:
    """List of legs in a route"""
    def __init__(self, cost: int, time: int, legs: list[LegId]):
        self.cost = cost
        self.time = time
        self.legs = legs
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "cost": self.cost,
            "time": self.time,
            "legs": [leg.to_dict() for leg in self.legs]
        }

# ============================================
# Constant List of Legs
# ============================================

# Create a comprehensive list of transportation legs
CONSTANT_LEGS = [
    # Domestic legs within Germany
    Leg("leg_berlin_leipzig", "DB_Cargo", "Berlin", "Leipzig", 1000.0, 3, 50, 0.3, 0.005),
    Leg("leg_berlin_hamburg", "DB_Cargo", "Berlin", "Hamburg", 1000.0, 4, 60, 0.35, 0.006),
    Leg("leg_berlin_frankfurt", "DB_Cargo", "Berlin", "Frankfurt", 1000.0, 5, 70, 0.4, 0.007),
    Leg("leg_leipzig_munich", "DB_Cargo", "Leipzig", "Munich", 800.0, 6, 80, 0.45, 0.008),
    Leg("leg_hamburg_cologne", "DB_Cargo", "Hamburg", "Cologne", 900.0, 5, 65, 0.38, 0.006),
    Leg("leg_frankfurt_stuttgart", "DB_Cargo", "Frankfurt", "Stuttgart", 700.0, 4, 55, 0.32, 0.005),
    Leg("leg_munich_stuttgart", "DB_Cargo", "Munich", "Stuttgart", 600.0, 3, 40, 0.28, 0.004),
    Leg("leg_cologne_dusseldorf", "DB_Cargo", "Cologne", "Dusseldorf", 500.0, 2, 25, 0.2, 0.003),
    
    # International legs
    Leg("leg_berlin_warsaw", "PKP_Cargo", "Berlin", "Warsaw", 1200.0, 8, 120, 0.5, 0.01),
    Leg("leg_warsaw_prague", "PKP_Cargo", "Warsaw", "Prague", 1100.0, 7, 110, 0.48, 0.009),
    Leg("leg_prague_vienna", "OBB_Cargo", "Prague", "Vienna", 900.0, 6, 90, 0.42, 0.008),
    Leg("leg_vienna_budapest", "OBB_Cargo", "Vienna", "Budapest", 800.0, 5, 85, 0.4, 0.008),
    Leg("leg_frankfurt_paris", "SNCF", "Frankfurt", "Paris", 1000.0, 8, 150, 0.55, 0.012),
    Leg("leg_paris_brussels", "SNCF", "Paris", "Brussels", 800.0, 4, 80, 0.35, 0.007),
    Leg("leg_brussels_amsterdam", "NMBS", "Brussels", "Amsterdam", 700.0, 3, 60, 0.3, 0.006),
    Leg("leg_hamburg_copenhagen", "DSB", "Hamburg", "Copenhagen", 900.0, 7, 130, 0.52, 0.011),
    
    # Air freight legs (faster but more expensive)
    Leg("leg_berlin_munich_air", "Lufthansa_Cargo", "Berlin", "Munich", 500.0, 2, 300, 1.0, 0.02),
    Leg("leg_frankfurt_london_air", "British_Airways_Cargo", "Frankfurt", "London", 400.0, 3, 350, 1.2, 0.025),
    Leg("leg_munich_rome_air", "Alitalia_Cargo", "Munich", "Rome", 450.0, 3, 320, 1.1, 0.022),
    
    # Hub connections
    Leg("leg_leipzig_hub", "DB_Express", "Leipzig", "Hub_Central", 2000.0, 4, 40, 0.25, 0.004),
    Leg("leg_hub_central_leipzig", "DB_Express", "Hub_Central", "Leipzig", 2000.0, 4, 40, 0.25, 0.004),
    Leg("leg_frankfurt_hub", "DB_Express", "Frankfurt", "Hub_Central", 2000.0, 3, 35, 0.22, 0.004),
    Leg("leg_hub_central_frankfurt", "DB_Express", "Hub_Central", "Frankfurt", 2000.0, 3, 35, 0.22, 0.004),
    Leg("leg_hub_central_munich", "DB_Express", "Hub_Central", "Munich", 2000.0, 6, 60, 0.35, 0.006),
    Leg("leg_munich_hub_central", "DB_Express", "Munich", "Hub_Central", 2000.0, 6, 60, 0.35, 0.006),
    
    # Regional/local legs
    Leg("leg_berlin_suburb", "Local_Courier", "Berlin", "Berlin_Suburb", 100.0, 2, 20, 0.4, 0.008),
    Leg("leg_munich_suburb", "Local_Courier", "Munich", "Munich_Suburb", 100.0, 2, 20, 0.4, 0.008),
    Leg("leg_frankfurt_suburb", "Local_Courier", "Frankfurt", "Frankfurt_Suburb", 100.0, 2, 20, 0.4, 0.008),
]

# Build location index for faster lookup
LOCATION_INDEX = {}
for leg in CONSTANT_LEGS:
    if leg.from_location not in LOCATION_INDEX:
        LOCATION_INDEX[leg.from_location] = []
    LOCATION_INDEX[leg.from_location].append(leg)

# ============================================
# Routing Service with Dijkstra's Algorithm
# ============================================

class RoutingService:
    """
    Routing service that uses Dijkstra's algorithm to find the optimal route
    based on cost optimization.
    """
    
    @staticmethod
    def compute_route(parcel: ParcelDescription) -> Optional[LegList]:
        """
        Compute the optimal route for a parcel using Dijkstra's algorithm
        to minimize cost.
        
        Args:
            parcel: The parcel description containing origin, destination, weight, and value
            
        Returns:
            LegList object with route details, or None if routing fails
        """
        try:
            # Validate inputs
            if (not parcel.from_location or not parcel.to_location or 
                parcel.weight <= 0 or parcel.value < 0):
                return None
            
            # Check if source and destination exist in our network
            if (parcel.from_location not in LOCATION_INDEX or 
                parcel.to_location not in [leg.to_location for leg in CONSTANT_LEGS]):
                app.logger.warning(f"Location not found in network: {parcel.from_location} or {parcel.to_location}")
                return None
            
            # Use Dijkstra's algorithm to find the cheapest route
            route = RoutingService._find_cheapest_route(
                parcel.from_location, 
                parcel.to_location, 
                parcel.weight, 
                parcel.value
            )
            
            if not route:
                return None
            
            # Calculate total cost and time
            total_cost = 0
            total_time = 0
            leg_ids = []
            
            for leg in route:
                total_cost += leg.cost(parcel.weight, parcel.value)
                total_time += leg.time
                leg_ids.append(LegId(leg.id))
            
            return LegList(
                cost=int(total_cost),
                time=int(total_time),
                legs=leg_ids
            )
            
        except Exception as e:
            app.logger.error(f"Routing error: {str(e)}")
            return None
    
    @staticmethod
    def _find_cheapest_route(start: str, end: str, weight: float, value: int) -> List[Leg]:
        """
        Dijkstra's algorithm implementation to find the cheapest route.
        
        Returns:
            List of legs representing the cheapest route from start to end
        """
        # Priority queue: (total_cost, current_location, path_legs)
        pq = []
        heapq.heappush(pq, (0, start, []))
        
        # Keep track of minimum costs to reach each location
        min_costs = {start: 0}
        visited = set()
        
        while pq:
            current_cost, current_loc, path = heapq.heappop(pq)
            
            # Skip if we've found a better way to this location
            if current_loc in visited and current_cost > min_costs.get(current_loc, float('inf')):
                continue
            
            visited.add(current_loc)
            
            # Check if we've reached the destination
            if current_loc == end:
                return path
            
            # Explore neighbors through available legs
            if current_loc not in LOCATION_INDEX:
                continue
            
            for leg in LOCATION_INDEX[current_loc]:
                # Skip if parcel is too heavy for this leg
                if weight > leg.max_weight:
                    continue
                
                # Calculate cost for this leg
                leg_cost = leg.cost(weight, value)
                total_cost = current_cost + leg_cost
                
                # Check if this is a better path to the next location
                if (leg.to_location not in min_costs or 
                    total_cost < min_costs[leg.to_location]):
                    
                    min_costs[leg.to_location] = total_cost
                    new_path = path + [leg]
                    heapq.heappush(pq, (total_cost, leg.to_location, new_path))
        
        # No path found
        return None
    
    @staticmethod
    def get_all_legs() -> List[Dict[str, Any]]:
        """Return all available legs (for debugging/monitoring)"""
        return [leg.to_dict() for leg in CONSTANT_LEGS]
    
    @staticmethod
    def get_locations() -> List[str]:
        """Return all unique locations in the network"""
        locations = set()
        for leg in CONSTANT_LEGS:
            locations.add(leg.from_location)
            locations.add(leg.to_location)
        return sorted(list(locations))

# ============================================
# Route Endpoint
# ============================================

@app.route('/route', methods=['POST'])
def route_parcel():
    """
    POST /route endpoint for computing parcel routes.
    
    Expected JSON body (ParcelDescription schema):
    {
        "from": "string",
        "to": "string",
        "weight": number,
        "value": integer
    }
    
    Returns:
        200: LegList JSON with route information
        400: Cannot create route for this parcel
    """
    # Validate request
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400
    
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['from', 'to', 'weight', 'value']
    missing_fields = [field for field in required_fields if field not in data]
    
    if missing_fields:
        return jsonify({
            "error": "Missing required fields",
            "missing": missing_fields
        }), 400
    
    try:
        # Parse parcel description
        parcel = ParcelDescription.from_dict(data)
        
        # Validate weight and value
        if parcel.weight <= 0:
            return jsonify({
                "error": "Invalid parcel weight",
                "message": "Weight must be greater than 0"
            }), 400
            
        if parcel.value < 0:
            return jsonify({
                "error": "Invalid parcel value",
                "message": "Value cannot be negative"
            }), 400
        
        # Compute route using routing service
        route = RoutingService.compute_route(parcel)
        
        if route is None:
            return jsonify({
                "error": "Cannot create route for this parcel",
                "message": "No valid route found for the given constraints"
            }), 400
        
        # Return successful response
        return jsonify(route.to_dict()), 200
        
    except ValueError as e:
        # Handle data validation errors
        return jsonify({
            "error": "Invalid data format",
            "message": str(e)
        }), 400
        
    except Exception as e:
        # Handle unexpected errors
        app.logger.error(f"Unexpected error in /route: {str(e)}")
        return jsonify({
            "error": "Internal server error",
            "message": "An unexpected error occurred"
        }), 500

# ============================================
# Additional Endpoints for Debugging/Monitoring
# ============================================

@app.route('/legs', methods=['GET'])
def get_legs():
    """GET endpoint to retrieve all available legs"""
    return jsonify({
        "legs": RoutingService.get_all_legs(),
        "count": len(CONSTANT_LEGS)
    }), 200

@app.route('/locations', methods=['GET'])
def get_locations():
    """GET endpoint to retrieve all available locations"""
    return jsonify({
        "locations": RoutingService.get_locations(),
        "count": len(RoutingService.get_locations())
    }), 200

@app.route('/route/debug', methods=['POST'])
def debug_route():
    """
    Debug endpoint that returns multiple possible routes with details
    """
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400
    
    data = request.get_json()
    
    try:
        parcel = ParcelDescription.from_dict(data)
        
        # Get all possible direct legs
        direct_legs = []
        for leg in CONSTANT_LEGS:
            if (leg.from_location == parcel.from_location and 
                leg.to_location == parcel.to_location and
                parcel.weight <= leg.max_weight):
                direct_legs.append({
                    "leg": leg.to_dict(),
                    "cost": leg.cost(parcel.weight, parcel.value),
                    "time": leg.time
                })
        
        # Get the optimal route
        optimal_route = RoutingService.compute_route(parcel)
        
        response = {
            "parcel": {
                "from": parcel.from_location,
                "to": parcel.to_location,
                "weight": parcel.weight,
                "value": parcel.value
            },
            "direct_options": sorted(direct_legs, key=lambda x: x["cost"]),
            "optimal_route": optimal_route.to_dict() if optimal_route else None
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        app.logger.error(f"Debug route error: {str(e)}")
        return jsonify({"error": str(e)}), 500

# ============================================
# Health Check (optional but recommended)
# ============================================

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "routing-service",
        "endpoints": [
            "POST /route",
            "GET /legs",
            "GET /locations",
            "POST /route/debug",
            "GET /health"
        ],
        "legs_count": len(CONSTANT_LEGS),
        "locations_count": len(RoutingService.get_locations())
    }), 200

# ============================================
# Error Handlers
# ============================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Not Found",
        "message": "The requested endpoint does not exist"
    }), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        "error": "Method Not Allowed",
        "message": "Check the endpoint documentation for supported methods"
    }), 405

# ============================================
# Main Application Entry Point
# ============================================

if __name__ == '__main__':
    # Configuration
    app.config['JSON_SORT_KEYS'] = False  # Maintain JSON key order
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
    
    # Print some startup information
    print(f"Routing Service Started")
    print(f"Available legs: {len(CONSTANT_LEGS)}")
    print(f"Available locations: {len(RoutingService.get_locations())}")
    print(f"Service running on http://0.0.0.0:5000")
    
    # Start the Flask development server
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )