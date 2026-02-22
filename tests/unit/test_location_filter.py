import pytest
from applypilot.discovery.jobspy import _location_ok

def test_location_ok_remote():
    assert _location_ok("Remote, NY", ["New York"], False) == True
    assert _location_ok("Work from home", ["Mars"], False) == True

def test_true_rejects_non_remote():
    assert _location_ok("New York, NY", ["New York"], True) == False
    assert _location_ok("San Francisco", ["New York"], True) == False
    assert _location_ok("Remote", ["New York"], True) == True

def test_list_rejects_custom():
    assert _location_ok("New York, NY", ["New York"], ["Texas", "California"]) == True
    assert _location_ok("Houston, Texas", ["New York"], ["Texas", "California"]) == False

def test_accepts_pattern():
    assert _location_ok("Chicago", ["Chicago", "Austin"], False) == True
    assert _location_ok("Miami", ["Chicago", "Austin"], False) == False
