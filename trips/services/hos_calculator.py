"""
HOS (Hours of Service) Calculator.
Implements FMCSA regulations for property-carrying drivers.
"""
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field


@dataclass
class HOSState:
    """Tracks the current HOS state."""
    driving_hours_today: float = 0.0          # 11-hour limit
    on_duty_hours_today: float = 0.0          # 14-hour window
    hours_since_last_break: float = 0.0       # 30-min break after 8 hours
    cycle_hours_used: float = 0.0             # 70-hour/8-day limit
    current_time: datetime = field(default_factory=datetime.now)
    current_miles: float = 0.0


class HOSCalculator:
    """
    Calculator for HOS-compliant trip planning.
    
    Rules implemented:
    - 11-hour driving limit (after 10 consecutive hours off)
    - 14-hour on-duty window
    - 30-minute break after 8 cumulative hours of driving
    - 70-hour/8-day cycle limit
    - 10-hour off-duty reset
    """
    
    # HOS Limits
    MAX_DRIVING_HOURS = 11.0
    MAX_ON_DUTY_HOURS = 14.0
    BREAK_REQUIRED_AFTER = 8.0
    MAX_CYCLE_HOURS = 70.0
    REQUIRED_REST_HOURS = 10.0
    REQUIRED_BREAK_MINUTES = 30
    
    # Trip assumptions
    AVERAGE_SPEED_MPH = 55
    FUEL_STOP_INTERVAL_MILES = 1000
    FUEL_STOP_DURATION_MINUTES = 30
    PICKUP_DURATION_MINUTES = 60
    DROPOFF_DURATION_MINUTES = 60
    PRE_TRIP_INSPECTION_MINUTES = 30
    POST_TRIP_INSPECTION_MINUTES = 15
    
    def __init__(self, start_time: datetime = None, current_cycle_hours: float = 0):
        """
        Initialize the HOS calculator.
        
        Args:
            start_time: When the trip starts (defaults to 6:00 AM today)
            current_cycle_hours: Hours already used in the 70-hour/8-day cycle
        """
        if start_time is None:
            today = datetime.now().replace(hour=6, minute=0, second=0, microsecond=0)
            start_time = today
        
        self.state = HOSState(
            cycle_hours_used=current_cycle_hours,
            current_time=start_time
        )
        self.stops: List[Dict] = []
        self.stop_id = 0
    
    def calculate_trip(
        self, 
        route_data: Dict,
        locations: Dict[str, Dict],
        geometry: List[Tuple[float, float]],
        geocoder
    ) -> List[Dict]:
        """
        Calculate all stops for an HOS-compliant trip.
        
        Args:
            route_data: Route information with distances and legs
            locations: Dict with 'current', 'pickup', 'dropoff' coordinates
            geometry: Route geometry as list of (lat, lng) tuples
            geocoder: GeocodingService instance for reverse geocoding
            
        Returns:
            List of planned stops
        """
        self.stops = []
        self.stop_id = 0
        
        total_distance = route_data['total_distance_miles']
        pickup_distance = route_data['legs'][0]['distance_miles']
        
        # 1. Start with pre-trip inspection at current location
        self._add_stop(
            stop_type='start',
            location=locations['current']['display_name'],
            coordinates=locations['current'],
            duration_minutes=self.PRE_TRIP_INSPECTION_MINUTES,
            duty_status='on_duty',
            notes='Pre-trip inspection'
        )
        
        # 2. Drive to pickup
        self._drive_segment(
            distance_miles=pickup_distance,
            geometry=geometry,
            geocoder=geocoder,
            end_location=locations['pickup']['display_name'],
            end_coords=locations['pickup']
        )
        
        # 3. Pickup stop
        self._add_stop(
            stop_type='pickup',
            location=locations['pickup']['display_name'],
            coordinates=locations['pickup'],
            duration_minutes=self.PICKUP_DURATION_MINUTES,
            duty_status='on_duty',
            notes='Loading cargo'
        )
        
        # 4. Drive to dropoff
        dropoff_distance = route_data['legs'][1]['distance_miles']
        self._drive_segment(
            distance_miles=dropoff_distance,
            geometry=geometry,
            geocoder=geocoder,
            start_miles=pickup_distance,
            end_location=locations['dropoff']['display_name'],
            end_coords=locations['dropoff']
        )
        
        # 5. Dropoff stop
        self._add_stop(
            stop_type='dropoff',
            location=locations['dropoff']['display_name'],
            coordinates=locations['dropoff'],
            duration_minutes=self.DROPOFF_DURATION_MINUTES,
            duty_status='on_duty',
            notes='Unloading cargo'
        )
        
        # 6. Post-trip inspection
        self._add_stop(
            stop_type='end',
            location=locations['dropoff']['display_name'],
            coordinates=locations['dropoff'],
            duration_minutes=self.POST_TRIP_INSPECTION_MINUTES,
            duty_status='on_duty',
            notes='Post-trip inspection'
        )
        
        return self.stops
    
    def _drive_segment(
        self,
        distance_miles: float,
        geometry: List[Tuple[float, float]],
        geocoder,
        end_location: str,
        end_coords: Dict,
        start_miles: float = 0
    ):
        """
        Process a driving segment, adding required stops.
        """
        from .routing import RoutingService
        routing = RoutingService()
        
        remaining_distance = distance_miles
        segment_start_miles = start_miles
        
        while remaining_distance > 0:
            # Calculate how far we can drive before hitting a limit
            miles_until_break = self._miles_until_break()
            miles_until_rest = self._miles_until_rest()
            miles_until_fuel = self._miles_until_fuel()
            
            # Find the limiting factor
            max_drivable = min(
                remaining_distance,
                miles_until_break,
                miles_until_rest,
                miles_until_fuel
            )
            
            if max_drivable <= 0:
                # Need to take a break/rest before continuing
                if self.state.driving_hours_today >= self.MAX_DRIVING_HOURS:
                    self._take_rest(geometry, geocoder, segment_start_miles + (distance_miles - remaining_distance))
                elif self.state.hours_since_last_break >= self.BREAK_REQUIRED_AFTER:
                    self._take_break(geometry, geocoder, segment_start_miles + (distance_miles - remaining_distance))
                continue
            
            # Drive the segment
            driving_hours = max_drivable / self.AVERAGE_SPEED_MPH
            self._update_state_for_driving(driving_hours, max_drivable)
            remaining_distance -= max_drivable
            
            # Check if we need a stop after this driving segment
            if remaining_distance > 0:
                current_miles = segment_start_miles + (distance_miles - remaining_distance)
                
                # Check which limit we hit
                if self.state.driving_hours_today >= self.MAX_DRIVING_HOURS:
                    self._take_rest(geometry, geocoder, current_miles)
                elif self.state.hours_since_last_break >= self.BREAK_REQUIRED_AFTER:
                    self._take_break(geometry, geocoder, current_miles)
                elif self._needs_fuel():
                    self._take_fuel_stop(geometry, geocoder, current_miles)
    
    def _miles_until_break(self) -> float:
        """Calculate miles until 30-minute break is required."""
        hours_left = self.BREAK_REQUIRED_AFTER - self.state.hours_since_last_break
        return max(0, hours_left * self.AVERAGE_SPEED_MPH)
    
    def _miles_until_rest(self) -> float:
        """Calculate miles until 10-hour rest is required."""
        hours_left = self.MAX_DRIVING_HOURS - self.state.driving_hours_today
        return max(0, hours_left * self.AVERAGE_SPEED_MPH)
    
    def _miles_until_fuel(self) -> float:
        """Calculate miles until fuel stop is needed."""
        miles_since_fuel = self.state.current_miles % self.FUEL_STOP_INTERVAL_MILES
        return self.FUEL_STOP_INTERVAL_MILES - miles_since_fuel
    
    def _needs_fuel(self) -> bool:
        """Check if a fuel stop is needed."""
        return self.state.current_miles > 0 and self.state.current_miles % self.FUEL_STOP_INTERVAL_MILES == 0
    
    def _update_state_for_driving(self, hours: float, miles: float):
        """Update HOS state after driving."""
        self.state.driving_hours_today += hours
        self.state.on_duty_hours_today += hours
        self.state.hours_since_last_break += hours
        self.state.cycle_hours_used += hours
        self.state.current_time += timedelta(hours=hours)
        self.state.current_miles += miles
    
    def _take_break(self, geometry, geocoder, current_miles: float):
        """Take a 30-minute break."""
        coords = self._get_coords_at_mile(geometry, current_miles)
        location = geocoder.reverse_geocode(coords[0], coords[1]) or 'Unknown Location'
        
        self._add_stop(
            stop_type='break',
            location=location,
            coordinates={'lat': coords[0], 'lng': coords[1]},
            duration_minutes=self.REQUIRED_BREAK_MINUTES,
            duty_status='off_duty',
            notes='30-minute break (8 hours driving)'
        )
        
        self.state.hours_since_last_break = 0
    
    def _take_rest(self, geometry, geocoder, current_miles: float):
        """Take a 10-hour rest."""
        coords = self._get_coords_at_mile(geometry, current_miles)
        location = geocoder.reverse_geocode(coords[0], coords[1]) or 'Unknown Location'
        
        self._add_stop(
            stop_type='rest',
            location=location,
            coordinates={'lat': coords[0], 'lng': coords[1]},
            duration_minutes=int(self.REQUIRED_REST_HOURS * 60),
            duty_status='off_duty',
            notes='10-hour rest (11-hour driving limit)'
        )
        
        # Reset daily limits
        self.state.driving_hours_today = 0
        self.state.on_duty_hours_today = 0
        self.state.hours_since_last_break = 0
        
        # Add pre-trip inspection after rest
        self._add_stop(
            stop_type='pre_trip',
            location=location,
            coordinates={'lat': coords[0], 'lng': coords[1]},
            duration_minutes=self.PRE_TRIP_INSPECTION_MINUTES,
            duty_status='on_duty',
            notes='Pre-trip inspection'
        )
    
    def _take_fuel_stop(self, geometry, geocoder, current_miles: float):
        """Take a fuel stop."""
        coords = self._get_coords_at_mile(geometry, current_miles)
        location = geocoder.reverse_geocode(coords[0], coords[1]) or 'Unknown Location'
        
        self._add_stop(
            stop_type='fuel',
            location=location,
            coordinates={'lat': coords[0], 'lng': coords[1]},
            duration_minutes=self.FUEL_STOP_DURATION_MINUTES,
            duty_status='on_duty',
            notes='Fuel stop (1,000 miles)'
        )
    
    def _get_coords_at_mile(self, geometry, miles: float) -> Tuple[float, float]:
        """Get coordinates at a specific mile point along the route."""
        from .routing import RoutingService
        routing = RoutingService()
        coords = routing.get_point_along_route(geometry, miles)
        return coords if coords else geometry[0]
    
    def _add_stop(
        self,
        stop_type: str,
        location: str,
        coordinates: Dict,
        duration_minutes: int,
        duty_status: str,
        notes: str
    ):
        """Add a stop to the list."""
        self.stop_id += 1
        
        # Calculate day number (1-indexed)
        start_of_trip = self.stops[0]['arrival_time'] if self.stops else self.state.current_time
        if isinstance(start_of_trip, str):
            start_of_trip = datetime.fromisoformat(start_of_trip)
        
        arrival_time = self.state.current_time
        departure_time = arrival_time + timedelta(minutes=duration_minutes)
        
        # Calculate day based on calendar date
        day = (arrival_time.date() - start_of_trip.date()).days + 1
        
        stop = {
            'id': self.stop_id,
            'type': stop_type,
            'location': self._format_location(location),
            'coordinates': {
                'lat': coordinates.get('lat', coordinates[0] if isinstance(coordinates, tuple) else 0),
                'lng': coordinates.get('lng', coordinates[1] if isinstance(coordinates, tuple) else 0)
            },
            'arrival_time': arrival_time.isoformat(),
            'departure_time': departure_time.isoformat(),
            'duration_minutes': duration_minutes,
            'cumulative_miles': round(self.state.current_miles, 1),
            'cumulative_driving_hours': round(self.state.driving_hours_today, 2),
            'day': day,
            'duty_status': duty_status,
            'notes': notes
        }
        
        self.stops.append(stop)
        
        # Update time for non-driving stops (on_duty time counts)
        if duty_status == 'on_duty':
            self.state.on_duty_hours_today += duration_minutes / 60
            self.state.cycle_hours_used += duration_minutes / 60
        
        self.state.current_time = departure_time
    
    def _format_location(self, location: str) -> str:
        """Format location to be more concise."""
        if not location:
            return 'Unknown Location'
        
        # Try to extract city and state
        parts = location.split(',')
        if len(parts) >= 2:
            city = parts[0].strip()
            # Look for state in the remaining parts
            for part in parts[1:]:
                part = part.strip()
                if len(part) == 2 and part.isupper():
                    return f"{city}, {part}"
                # Check for state names
                if part in ['California', 'Arizona', 'Texas', 'New Mexico', 'Nevada', 'Oklahoma', 'Arkansas', 'Louisiana', 'Mississippi', 'Alabama', 'Georgia', 'Florida', 'South Carolina', 'North Carolina', 'Virginia', 'Tennessee', 'Kentucky', 'Missouri', 'Kansas', 'Colorado', 'Utah', 'Oregon', 'Washington', 'Idaho', 'Montana', 'Wyoming', 'Nebraska', 'South Dakota', 'North Dakota', 'Minnesota', 'Iowa', 'Wisconsin', 'Illinois', 'Indiana', 'Ohio', 'Michigan', 'Pennsylvania', 'New York', 'New Jersey', 'Maryland', 'Delaware', 'Connecticut', 'Massachusetts', 'Rhode Island', 'Vermont', 'New Hampshire', 'Maine']:
                    abbrev = self._state_to_abbrev(part)
                    return f"{city}, {abbrev}"
        
        return location[:50] if len(location) > 50 else location
    
    def _state_to_abbrev(self, state: str) -> str:
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
            'Wisconsin': 'WI', 'Wyoming': 'WY'
        }
        return states.get(state, state[:2].upper())
    
    def get_summary(self, total_distance: float) -> Dict:
        """Get trip summary statistics."""
        fuel_stops = sum(1 for s in self.stops if s['type'] == 'fuel')
        rest_breaks = sum(1 for s in self.stops if s['type'] == 'break')
        rest_stops = sum(1 for s in self.stops if s['type'] == 'rest')
        
        # Calculate total duration
        if self.stops:
            start_time = datetime.fromisoformat(self.stops[0]['arrival_time'])
            end_time = datetime.fromisoformat(self.stops[-1]['departure_time'])
            total_hours = (end_time - start_time).total_seconds() / 3600
            total_days = max(1, self.stops[-1]['day'])
        else:
            total_hours = 0
            total_days = 0
        
        return {
            'total_distance_miles': round(total_distance, 1),
            'total_duration_hours': round(total_hours, 1),
            'total_days': total_days,
            'fuel_stops': fuel_stops,
            'rest_breaks': rest_breaks,
            'rest_stops': rest_stops,
            'cycle_hours_after': round(self.state.cycle_hours_used, 1)
        }
