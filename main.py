from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
import pytz
import pycountry
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI(
    title="City Timezone Converter API",
    description="Convert time between two cities using timezone and geolocation data.",
    version="1.0.0"
)
# Setup
geolocator = Nominatim(user_agent="timezone-api", timeout=5)
tz_finder = TimezoneFinder()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
# --- Utility ---


def normalize_country_name(code_or_name: str) -> str:
    if not code_or_name:
        return "Unknown"
    code_or_name = code_or_name.strip()
    # Try exact alpha_2 or alpha_3 match
    country = pycountry.countries.get(alpha_2=code_or_name.upper())
    if country:
        return country.name
    country = pycountry.countries.get(alpha_3=code_or_name.upper())
    if country:
        return country.name
    # Fallback: search substring in names (less precise)
    try:
        for c in pycountry.countries:
            if code_or_name.lower() in c.name.lower() or \
               code_or_name.lower() in getattr(c, "official_name", "").lower():
                return c.name
    except:
        pass
    return code_or_name  # fallback



class TimeRequest(BaseModel):
    from_city: str  # Format: "City, Country" recommended
    to_city: str
    time: str       # Format: "YYYY-MM-DD HH:MM"
# --- Health Check ---


@app.get("/", tags=["Health"])
def root():
    return {"message": "✅ City Timezone Converter API is online."}
# --- Main Conversion ---


@app.post("/convert-time", tags=["Conversion"])
def convert_time(req: TimeRequest):
    try:
        # Validate datetime format
        try:
            naive_dt = datetime.strptime(req.time.strip(), "%Y-%m-%d %H:%M")
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Time must be in format YYYY-MM-DD HH:MM")
        # Geocode input cities
        from_location = geolocator.geocode(req.from_city, addressdetails=True)
        to_location = geolocator.geocode(req.to_city, addressdetails=True)
        if not from_location or not to_location:
            raise HTTPException(
                status_code=404, detail="One or both cities could not be found.")
        # Extract and normalize country names
        raw_from_code = from_location.raw.get(
            "address", {}).get("country_code", None)
        raw_to_code = to_location.raw.get(
            "address", {}).get("country_code", None)
        from_country = normalize_country_name(
            raw_from_code) if raw_from_code else "Unknown"
        to_country = normalize_country_name(
            raw_to_code) if raw_to_code else "Unknown"
        # Determine timezones
        from_tz_name = tz_finder.timezone_at(
            lat=from_location.latitude, lng=from_location.longitude)
        to_tz_name = tz_finder.timezone_at(
            lat=to_location.latitude, lng=to_location.longitude)
        if not from_tz_name or not to_tz_name:
            raise HTTPException(
                status_code=404, detail="Could not determine timezone for one or both cities.")
        # Convert time
        from_tz = pytz.timezone(from_tz_name)
        to_tz = pytz.timezone(to_tz_name)
        from_dt = from_tz.localize(naive_dt)
        to_dt = from_dt.astimezone(to_tz)
        # Time difference
        from_offset = from_dt.utcoffset().total_seconds() / 3600
        to_offset = to_dt.utcoffset().total_seconds() / 3600
        diff_hours = int(to_offset - from_offset)
        return {
            "converted_time": to_dt.strftime("%Y-%m-%d %H:%M"),
            "from_city": req.from_city,
            "from_country": from_country,
            "from_timezone": from_tz_name,
            "to_city": req.to_city,
            "to_country": to_country,
            "to_timezone": to_tz_name,
            "difference_hours": diff_hours,
            "status": "success"
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
