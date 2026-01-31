# Spotter Backend

Django REST Framework backend for the Spotter ELD Trip Planner application. This service handles trip planning with HOS (Hours of Service) compliance calculations.

## 🚛 Features

- **Geocoding Service** - Convert addresses to coordinates using Nominatim API
- **Routing Service** - Calculate routes using OSRM (Open Source Routing Machine)
- **HOS Calculator** - Enforce FMCSA Hours of Service regulations
- **ELD Log Generator** - Generate compliant daily log sheets

## 📋 HOS Rules Implemented

| Rule | Limit | Description |
|------|-------|-------------|
| 11-Hour Driving | 11 hrs | Max driving after 10 consecutive hours off duty |
| 14-Hour Window | 14 hrs | Cannot drive after 14th hour since coming on duty |
| 30-Minute Break | Required | Must take 30-min break after 8 cumulative hours of driving |
| 10-Hour Off-Duty | 10 hrs | Required to reset the 11-hour and 14-hour clocks |
| 70-Hour/8-Day | 70 hrs | Cannot drive after 70 on-duty hours in 8 consecutive days |

## 🛠️ Tech Stack

- Python 3.10+
- Django 4.2
- Django REST Framework
- Requests (for external APIs)
- Polyline (for route geometry decoding)

## 📦 Installation

### Prerequisites
- Python 3.10 or higher
- pip

### Setup

```bash
# Clone the repository
git clone https://github.com/syedmustafan/spotter-backend.git
cd spotter-backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Start the development server
python manage.py runserver
```

The API will be available at `http://localhost:8000`

## 🔌 API Endpoints

### Plan Trip
```http
POST /api/plan-trip/
Content-Type: application/json

{
  "current_location": "Los Angeles, CA",
  "pickup_location": "Phoenix, AZ",
  "dropoff_location": "Dallas, TX",
  "current_cycle_hours": 20
}
```

**Response:**
```json
{
  "route_geometry": [[lat, lng], ...],
  "stops": [
    {
      "id": 1,
      "type": "start",
      "location": "Los Angeles, CA",
      "coordinates": {"lat": 34.05, "lng": -118.24},
      "arrival_time": "2026-01-31T06:00:00",
      "departure_time": "2026-01-31T06:30:00",
      "duration_minutes": 30,
      "cumulative_miles": 0,
      "day": 1,
      "notes": "Pre-trip inspection"
    }
  ],
  "log_sheets": [...],
  "summary": {
    "total_distance_miles": 1180,
    "total_duration_hours": 35,
    "total_days": 2,
    "fuel_stops": 1,
    "rest_breaks": 2,
    "rest_stops": 1,
    "cycle_hours_after": 41.5
  }
}
```

### Health Check
```http
GET /api/health/
```

## 📁 Project Structure

```
spotter-backend/
├── manage.py
├── requirements.txt
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── trips/
    ├── __init__.py
    ├── models.py
    ├── serializers.py
    ├── views.py
    ├── urls.py
    └── services/
        ├── __init__.py
        ├── geocoding.py      # Nominatim API integration
        ├── routing.py        # OSRM routing
        ├── hos_calculator.py # HOS rules engine
        └── log_generator.py  # ELD log sheet generation
```

## ⚙️ Configuration

Environment variables (optional):
- `DJANGO_SECRET_KEY` - Django secret key (default: dev key)
- `DEBUG` - Enable debug mode (default: True)

## 🧪 Trip Assumptions

| Parameter | Value |
|-----------|-------|
| Average driving speed | 55 mph |
| Fuel stop interval | Every 1,000 miles |
| Fuel stop duration | 30 minutes |
| Pickup duration | 1 hour |
| Dropoff duration | 1 hour |
| Pre-trip inspection | 30 minutes |
| Post-trip inspection | 15 minutes |

## 📄 License

MIT License

## 🔗 Related

- [Spotter Frontend](https://github.com/syedmustafan/spotter-frontend) - React frontend application
