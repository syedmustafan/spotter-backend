"""
Log Generator for ELD daily log sheets.
Creates 24-hour log sheets with duty status segments.
"""
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict


class LogGenerator:
    """
    Generates ELD daily log sheets from trip stops.
    
    Each log sheet covers a 24-hour period (midnight to midnight).
    The duty status line is continuous through the entire period.
    """
    
    def __init__(self):
        self.log_sheets: List[Dict] = []
    
    def generate_logs(self, stops: List[Dict]) -> List[Dict]:
        """
        Generate daily log sheets from trip stops.
        
        Args:
            stops: List of planned stops with timing information
            
        Returns:
            List of daily log sheets
        """
        if not stops:
            return []
        
        # First, create a timeline of all events
        events = self._create_event_timeline(stops)
        
        # Get the date range
        first_event = min(events, key=lambda x: x['time'])
        last_event = max(events, key=lambda x: x['time'])
        
        start_date = datetime.fromisoformat(first_event['time']).date()
        end_date = datetime.fromisoformat(last_event['time']).date()
        
        # Generate log for each day
        self.log_sheets = []
        current_date = start_date
        day_num = 1
        
        while current_date <= end_date:
            log_sheet = self._create_day_log(current_date, day_num, events, stops)
            self.log_sheets.append(log_sheet)
            current_date += timedelta(days=1)
            day_num += 1
        
        return self.log_sheets
    
    def _create_event_timeline(self, stops: List[Dict]) -> List[Dict]:
        """Create a flat timeline of all duty status changes."""
        events = []
        
        for i, stop in enumerate(stops):
            arrival = stop['arrival_time']
            departure = stop['departure_time']
            stop_type = stop.get('type', '')
            
            # Determine status for this stop
            if stop_type in ['rest', 'break']:
                status = 'off_duty'
            elif stop.get('duty_status') == 'off_duty':
                status = 'off_duty'
            else:
                status = 'on_duty'
            
            # Add arrival event (start of stop activity)
            events.append({
                'time': arrival,
                'status': status,
                'location': stop['location'],
                'notes': stop.get('notes', ''),
                'type': 'stop_start',
                'stop_type': stop_type
            })
            
            # Add departure event (end of stop, start driving to next)
            # Check if there's a next stop to drive to
            if i < len(stops) - 1:
                next_stop = stops[i + 1]
                # If this stop's departure leads to driving
                events.append({
                    'time': departure,
                    'status': 'driving',
                    'location': 'En route',
                    'notes': f"Driving to {next_stop['location']}",
                    'type': 'driving_start',
                    'stop_type': 'driving'
                })
            else:
                # Last stop - go off duty after
                events.append({
                    'time': departure,
                    'status': 'off_duty',
                    'location': stop['location'],
                    'notes': 'Trip complete',
                    'type': 'trip_end',
                    'stop_type': 'end'
                })
        
        # Sort by time
        events.sort(key=lambda x: x['time'])
        
        return events
    
    def _create_day_log(
        self, 
        date, 
        day_num: int, 
        events: List[Dict],
        stops: List[Dict]
    ) -> Dict:
        """Create a log sheet for a single day."""
        if isinstance(date, str):
            date = datetime.strptime(date, '%Y-%m-%d').date()
        
        midnight_start = datetime.combine(date, datetime.min.time())
        midnight_end = midnight_start + timedelta(days=1)
        
        # Generate segments for this day
        segments = self._generate_day_segments(midnight_start, midnight_end, events, day_num)
        
        # Calculate totals
        totals = self._calculate_totals(segments)
        
        # Calculate miles for this day
        total_miles = self._calculate_day_miles(date, stops)
        
        # Generate remarks for stops on this day
        remarks = self._generate_remarks(date, stops)
        
        return {
            'date': date.strftime('%m/%d/%Y'),
            'day_number': day_num,
            'total_miles': round(total_miles, 1),
            'segments': segments,
            'totals': totals,
            'remarks': remarks
        }
    
    def _generate_day_segments(
        self,
        day_start: datetime,
        day_end: datetime,
        events: List[Dict],
        day_num: int
    ) -> List[Dict]:
        """Generate duty status segments for a 24-hour period."""
        segments = []
        
        # Find events relevant to this day
        day_events = []
        
        for event in events:
            event_time = datetime.fromisoformat(event['time'])
            if event_time >= day_start and event_time < day_end:
                day_events.append({
                    **event,
                    'datetime': event_time
                })
        
        # Find what status we're in at the start of the day
        initial_status = self._get_status_at_time(day_start, events, day_num)
        
        # Build segments
        current_hour = 0.0
        current_status = initial_status['status']
        current_location = initial_status.get('location', '')
        
        for event in day_events:
            event_hour = self._time_to_hours(event['datetime'])
            
            # Add segment from current position to this event
            if event_hour > current_hour + 0.001:  # Small tolerance
                segments.append({
                    'status': current_status,
                    'start_hour': round(current_hour, 2),
                    'end_hour': round(event_hour, 2),
                    'location': current_location,
                    'notes': ''
                })
            
            # Update current status
            current_hour = event_hour
            current_status = event['status']
            current_location = event.get('location', '')
        
        # Fill to end of day
        if current_hour < 24.0:
            segments.append({
                'status': current_status,
                'start_hour': round(current_hour, 2),
                'end_hour': 24.0,
                'location': current_location,
                'notes': ''
            })
        
        # Merge consecutive segments with same status
        segments = self._merge_segments(segments)
        
        # Validate total = 24
        segments = self._normalize_segments(segments)
        
        return segments
    
    def _get_status_at_time(self, target_time: datetime, events: List[Dict], day_num: int) -> Dict:
        """Determine what duty status we're in at a specific time."""
        # Default to off_duty for the first day
        if day_num == 1:
            return {'status': 'off_duty', 'location': ''}
        
        # Find the last event before target_time
        last_event = None
        for event in events:
            event_time = datetime.fromisoformat(event['time'])
            if event_time < target_time:
                last_event = event
            else:
                break
        
        if last_event:
            return {
                'status': last_event['status'],
                'location': last_event.get('location', '')
            }
        
        return {'status': 'off_duty', 'location': ''}
    
    def _time_to_hours(self, dt: datetime) -> float:
        """Convert datetime to hours since midnight of that day."""
        return dt.hour + dt.minute / 60.0 + dt.second / 3600.0
    
    def _merge_segments(self, segments: List[Dict]) -> List[Dict]:
        """Merge consecutive segments with the same status."""
        if not segments:
            return []
        
        merged = [segments[0].copy()]
        
        for segment in segments[1:]:
            if segment['status'] == merged[-1]['status']:
                # Merge by extending end_hour
                merged[-1]['end_hour'] = segment['end_hour']
                # Keep location if we don't have one
                if segment['location'] and not merged[-1]['location']:
                    merged[-1]['location'] = segment['location']
            else:
                merged.append(segment.copy())
        
        return merged
    
    def _normalize_segments(self, segments: List[Dict]) -> List[Dict]:
        """Ensure segments cover exactly 24 hours with no gaps or overlaps."""
        if not segments:
            return [{'status': 'off_duty', 'start_hour': 0.0, 'end_hour': 24.0, 'location': '', 'notes': ''}]
        
        normalized = []
        
        for i, segment in enumerate(segments):
            start = segment['start_hour']
            end = segment['end_hour']
            
            # Fix any gaps from previous segment
            if normalized:
                prev_end = normalized[-1]['end_hour']
                if start > prev_end + 0.001:
                    # There's a gap - extend previous segment
                    normalized[-1]['end_hour'] = start
            
            # Add this segment
            normalized.append({
                'status': segment['status'],
                'start_hour': round(start, 1),
                'end_hour': round(end, 1),
                'location': segment.get('location', ''),
                'notes': segment.get('notes', '')
            })
        
        # Ensure first segment starts at 0
        if normalized and normalized[0]['start_hour'] > 0:
            normalized[0]['start_hour'] = 0.0
        
        # Ensure last segment ends at 24
        if normalized and normalized[-1]['end_hour'] < 24.0:
            normalized[-1]['end_hour'] = 24.0
        
        return normalized
    
    def _calculate_totals(self, segments: List[Dict]) -> Dict:
        """Calculate total hours for each duty status."""
        totals = {
            'off_duty': 0.0,
            'sleeper': 0.0,
            'driving': 0.0,
            'on_duty': 0.0
        }
        
        for segment in segments:
            status = segment['status']
            hours = segment['end_hour'] - segment['start_hour']
            if status in totals and hours > 0:
                totals[status] += hours
        
        # Round to 1 decimal place
        for key in totals:
            totals[key] = round(totals[key], 1)
        
        # Verify total is 24 (with small tolerance for rounding)
        total = sum(totals.values())
        if abs(total - 24.0) > 0.5:
            # Adjust the largest value to make it 24
            diff = 24.0 - total
            max_key = max(totals, key=totals.get)
            totals[max_key] = round(totals[max_key] + diff, 1)
        
        return totals
    
    def _calculate_day_miles(self, date, stops: List[Dict]) -> float:
        """Calculate miles driven on a specific day."""
        day_start = datetime.combine(date, datetime.min.time())
        day_end = day_start + timedelta(days=1)
        
        day_stops = []
        for stop in stops:
            arrival = datetime.fromisoformat(stop['arrival_time'])
            if day_start <= arrival < day_end:
                day_stops.append(stop)
        
        if not day_stops:
            return 0.0
        
        # Get miles range for this day
        first_miles = day_stops[0]['cumulative_miles']
        last_miles = day_stops[-1]['cumulative_miles']
        
        # For day 1, start from 0
        if date == datetime.fromisoformat(stops[0]['arrival_time']).date():
            return last_miles
        
        # Find the last stop from previous day
        prev_day_miles = 0.0
        for stop in stops:
            arrival = datetime.fromisoformat(stop['arrival_time'])
            if arrival < day_start:
                prev_day_miles = stop['cumulative_miles']
            else:
                break
        
        return last_miles - prev_day_miles
    
    def _generate_remarks(self, date, stops: List[Dict]) -> List[Dict]:
        """Generate remarks section with location changes for a specific day."""
        remarks = []
        day_start = datetime.combine(date, datetime.min.time())
        day_end = day_start + timedelta(days=1)
        
        for stop in stops:
            arrival = datetime.fromisoformat(stop['arrival_time'])
            if day_start <= arrival < day_end:
                remarks.append({
                    'time': arrival.strftime('%H:%M'),
                    'location': stop['location'],
                    'activity': stop.get('notes', stop['type'])
                })
        
        return remarks
