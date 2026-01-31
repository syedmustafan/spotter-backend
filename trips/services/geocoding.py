"""
Geocoding service using Nominatim API.
Converts addresses to coordinates and vice versa.
"""
import requests
import time
from typing import Optional, Tuple, Dict


class GeocodingService:
    """Service for geocoding addresses using Nominatim (OpenStreetMap)."""
    
    BASE_URL = "https://nominatim.openstreetmap.org"
    USER_AGENT = "ELDTripPlanner/1.0"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.USER_AGENT
        })
        self._last_request_time = 0
    
    def _rate_limit(self):
        """Ensure we don't exceed Nominatim's rate limit (1 request/second)."""
        elapsed = time.time() - self._last_request_time
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        self._last_request_time = time.time()
    
    def geocode(self, address: str) -> Optional[Dict]:
        """
        Convert an address to coordinates.
        
        Args:
            address: The address string to geocode
            
        Returns:
            Dict with lat, lng, display_name or None if not found
        """
        self._rate_limit()
        
        try:
            response = self.session.get(
                f"{self.BASE_URL}/search",
                params={
                    'q': address,
                    'format': 'json',
                    'limit': 1,
                    'countrycodes': 'us'
                }
            )
            response.raise_for_status()
            results = response.json()
            
            if results:
                result = results[0]
                return {
                    'lat': float(result['lat']),
                    'lng': float(result['lon']),
                    'display_name': result['display_name']
                }
            return None
        except Exception as e:
            print(f"Geocoding error: {e}")
            return None
    
    def reverse_geocode(self, lat: float, lng: float) -> Optional[str]:
        """
        Convert coordinates to a location name.
        
        Args:
            lat: Latitude
            lng: Longitude
            
        Returns:
            Location name string (City, State) or None
        """
        self._rate_limit()
        
        try:
            response = self.session.get(
                f"{self.BASE_URL}/reverse",
                params={
                    'lat': lat,
                    'lon': lng,
                    'format': 'json',
                    'zoom': 10  # City level
                }
            )
            response.raise_for_status()
            result = response.json()
            
            if 'address' in result:
                addr = result['address']
                city = addr.get('city') or addr.get('town') or addr.get('village') or addr.get('county', '')
                state = addr.get('state', '')
                
                # Get state abbreviation
                state_abbr = self._get_state_abbreviation(state)
                
                if city and state_abbr:
                    return f"{city}, {state_abbr}"
                elif city:
                    return city
            
            return result.get('display_name', 'Unknown Location')
        except Exception as e:
            print(f"Reverse geocoding error: {e}")
            return None
    
    def _get_state_abbreviation(self, state_name: str) -> str:
        """Convert state name to abbreviation."""
        states = {
            'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR',
            'California': 'CA', 'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE',
            'Florida': 'FL', 'Georgia': 'GA', 'Hawaii': 'HI', 'Idaho': 'ID',
            'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA', 'Kansas': 'KS',
            'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
            'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS',
            'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV',
            'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY',
            'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK',
            'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
            'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT',
            'Vermont': 'VT', 'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV',
            'Wisconsin': 'WI', 'Wyoming': 'WY', 'District of Columbia': 'DC'
        }
        return states.get(state_name, state_name[:2].upper() if state_name else '')
