"""
Views for ELD Trip Planner API.
"""
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializers import TripInputSerializer
from .services import GeocodingService, RoutingService, HOSCalculator, LogGenerator


@api_view(['POST'])
def plan_trip(request):
    """
    Plan a trip with HOS compliance.
    
    Request body:
    {
        "current_location": "Los Angeles, CA",
        "pickup_location": "Phoenix, AZ",
        "dropoff_location": "Dallas, TX",
        "current_cycle_hours": 20
    }
    
    Returns:
    {
        "route_geometry": [[lat, lng], ...],
        "stops": [...],
        "log_sheets": [...],
        "summary": {...}
    }
    """
    serializer = TripInputSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    data = serializer.validated_data
    
    # Initialize services
    geocoder = GeocodingService()
    router = RoutingService()
    
    try:
        # 1. Geocode all locations
        locations = {}
        for key, field in [
            ('current', 'current_location'),
            ('pickup', 'pickup_location'),
            ('dropoff', 'dropoff_location')
        ]:
            result = geocoder.geocode(data[field])
            if not result:
                return Response(
                    {'error': f'Could not find location: {data[field]}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            locations[key] = result
        
        # 2. Get route through all waypoints
        waypoints = [
            {'lat': locations['current']['lat'], 'lng': locations['current']['lng']},
            {'lat': locations['pickup']['lat'], 'lng': locations['pickup']['lng']},
            {'lat': locations['dropoff']['lat'], 'lng': locations['dropoff']['lng']}
        ]
        
        route = router.get_route(waypoints)
        if not route:
            return Response(
                {'error': 'Could not calculate route between locations'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 3. Calculate HOS-compliant stops
        hos = HOSCalculator(current_cycle_hours=data['current_cycle_hours'])
        stops = hos.calculate_trip(
            route_data=route,
            locations=locations,
            geometry=route['geometry'],
            geocoder=geocoder
        )
        
        # 4. Generate ELD log sheets
        log_gen = LogGenerator()
        log_sheets = log_gen.generate_logs(stops)
        
        # 5. Get trip summary
        summary = hos.get_summary(route['total_distance_miles'])
        
        # Prepare response
        response_data = {
            'route_geometry': route['geometry'],
            'stops': stops,
            'log_sheets': log_sheets,
            'summary': summary
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response(
            {'error': f'An error occurred while planning the trip: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def health_check(request):
    """Health check endpoint."""
    return Response({'status': 'healthy'}, status=status.HTTP_200_OK)
