"""
Models for ELD Trip Planner.
"""
from django.db import models


class Trip(models.Model):
    """Trip model to store trip planning requests."""
    current_location = models.CharField(max_length=500)
    pickup_location = models.CharField(max_length=500)
    dropoff_location = models.CharField(max_length=500)
    current_cycle_hours = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Trip from {self.current_location} to {self.dropoff_location}"
