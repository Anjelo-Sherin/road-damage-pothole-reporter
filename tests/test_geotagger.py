import pytest
from src.geotagger import haversine_distance_meters, GPXTrack, generate_sample_track

def test_haversine_distance():
    # Distance between Bangalore City Center and nearby point (~111 km per latitude degree)
    lat1, lon1 = 12.9716, 77.5946
    lat2, lon2 = 12.9726, 77.5946
    dist = haversine_distance_meters(lat1, lon1, lat2, lon2)
    assert 100 < dist < 125  # ~111 meters

def test_gpx_interpolation():
    track_pts = generate_sample_track(start_lat=12.9716, start_lon=77.5946, duration_sec=20.0)
    gpx = GPXTrack(track_pts)

    pos_mid = gpx.get_position_at_time(10.0)
    assert "lat" in pos_mid
    assert "lon" in pos_mid
    assert pos_mid["timestamp_sec"] == 10.0
    assert pos_mid["lat"] != track_pts[0]["lat"]
