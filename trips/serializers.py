"""
Serializers for ELD Trip Planner API.
"""
from rest_framework import serializers


class TripInputSerializer(serializers.Serializer):
    """Serializer for trip planning input."""
    current_location = serializers.CharField(max_length=500)
    pickup_location = serializers.CharField(max_length=500)
    dropoff_location = serializers.CharField(max_length=500)
    current_cycle_hours = serializers.FloatField(min_value=0, max_value=70)


class CoordinateSerializer(serializers.Serializer):
    """Serializer for coordinates."""
    lat = serializers.FloatField()
    lng = serializers.FloatField()


class StopSerializer(serializers.Serializer):
    """Serializer for a planned stop."""
    id = serializers.IntegerField()
    type = serializers.CharField()
    location = serializers.CharField()
    coordinates = CoordinateSerializer()
    arrival_time = serializers.CharField()
    departure_time = serializers.CharField()
    duration_minutes = serializers.IntegerField()
    cumulative_miles = serializers.FloatField()
    cumulative_driving_hours = serializers.FloatField()
    day = serializers.IntegerField()
    notes = serializers.CharField(allow_blank=True)


class DutySegmentSerializer(serializers.Serializer):
    """Serializer for a duty segment on the log sheet."""
    status = serializers.CharField()
    start_hour = serializers.FloatField()
    end_hour = serializers.FloatField()
    location = serializers.CharField()
    notes = serializers.CharField(allow_blank=True)


class LogSheetSerializer(serializers.Serializer):
    """Serializer for a daily log sheet."""
    date = serializers.CharField()
    day_number = serializers.IntegerField()
    total_miles = serializers.FloatField()
    segments = DutySegmentSerializer(many=True)
    totals = serializers.DictField()
    remarks = serializers.ListField(child=serializers.DictField())


class TripSummarySerializer(serializers.Serializer):
    """Serializer for trip summary."""
    total_distance_miles = serializers.FloatField()
    total_duration_hours = serializers.FloatField()
    total_days = serializers.IntegerField()
    fuel_stops = serializers.IntegerField()
    rest_breaks = serializers.IntegerField()
    rest_stops = serializers.IntegerField()
    cycle_hours_after = serializers.FloatField()


class TripResponseSerializer(serializers.Serializer):
    """Serializer for the complete trip response."""
    route_geometry = serializers.ListField(child=serializers.ListField())
    stops = StopSerializer(many=True)
    log_sheets = LogSheetSerializer(many=True)
    summary = TripSummarySerializer()
