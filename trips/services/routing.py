"""
Routing service using OSRM (Open Source Routing Machine).
Gets routes, distances, and route geometry.
"""
import requests
from typing import List, Dict, Optional, Tuple
import polyline


class RoutingService:
    """Service for getting routes using OSRM."""
    
    BASE_URL = "https://router.project-osrm.org/route/v1/driving"
    
    def __init__(self):
        self.session = requests.Session()
    
    def get_route(self, waypoints: List[Dict]) -> Optional[Dict]:
        """
        Get a route through multiple waypoints.
        
        Args:
            waypoints: List of dicts with 'lat' and 'lng' keys
            
        Returns:
            Dict with distance, duration, and geometry
        """
        if len(waypoints) < 2:
            return None
        
        # Build coordinates string: lng,lat;lng,lat;...
        coords = ';'.join([f"{w['lng']},{w['lat']}" for w in waypoints])
        
        try:
            response = self.session.get(
                f"{self.BASE_URL}/{coords}",
                params={
                    'overview': 'full',
                    'geometries': 'polyline',
                    'steps': 'true'
                }
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') != 'Ok':
                print(f"OSRM error: {data.get('message', 'Unknown error')}")
                return None
            
            route = data['routes'][0]
            
            # Decode the polyline geometry to lat/lng pairs
            geometry = polyline.decode(route['geometry'])
            
            # Get leg distances
            legs = []
            for leg in route['legs']:
                legs.append({
                    'distance_miles': leg['distance'] / 1609.34,  # meters to miles
                    'duration_hours': leg['duration'] / 3600      # seconds to hours
                })
            
            return {
                'total_distance_miles': route['distance'] / 1609.34,
                'total_duration_hours': route['duration'] / 3600,
                'geometry': geometry,  # List of [lat, lng] pairs
                'legs': legs
            }
        except Exception as e:
            print(f"Routing error: {e}")
            return None
    
    def get_point_along_route(
        self, 
        geometry: List[Tuple[float, float]], 
        target_distance_miles: float
    ) -> Optional[Tuple[float, float]]:
        """
        Find a point along the route at a specific distance.
        
        Args:
            geometry: List of (lat, lng) tuples
            target_distance_miles: Distance in miles from the start
            
        Returns:
            (lat, lng) tuple or None
        """
        if not geometry or target_distance_miles <= 0:
            return geometry[0] if geometry else None
        
        cumulative_distance = 0.0
        
        for i in range(len(geometry) - 1):
            segment_distance = self._haversine_distance(
                geometry[i][0], geometry[i][1],
                geometry[i + 1][0], geometry[i + 1][1]
            )
            
            if cumulative_distance + segment_distance >= target_distance_miles:
                # Interpolate within this segment
                remaining = target_distance_miles - cumulative_distance
                ratio = remaining / segment_distance if segment_distance > 0 else 0
                
                lat = geometry[i][0] + ratio * (geometry[i + 1][0] - geometry[i][0])
                lng = geometry[i][1] + ratio * (geometry[i + 1][1] - geometry[i][1])
                
                return (lat, lng)
            
            cumulative_distance += segment_distance
        
        # Return last point if distance exceeds route length
        return geometry[-1]
    
    def _haversine_distance(
        self, 
        lat1: float, 
        lng1: float, 
        lat2: float, 
        lng2: float
    ) -> float:
        """
        Calculate the distance between two points in miles.
        """
        from math import radians, sin, cos, sqrt, atan2
        
        R = 3959  # Earth's radius in miles
        
        lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
        
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        
        a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlng / 2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        
        return R * c
