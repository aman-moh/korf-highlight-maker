import pytest

# Assume these functions will exist in highlight_maker.py
# We are only writing tests for them here.
from highlight_maker import (
    parse_description_line,
    convert_timestamp_to_seconds,
    filter_timestamps_by_keywords,
    sanitize_filename
)

# --- Test Timestamp Parsing ---

@pytest.mark.parametrize("line, expected_timestamp, expected_text", [
    ("00:45 Goal Team A", "00:45", "Goal Team A"),
    ("1:23:45 Highlight Moment", "1:23:45", "Highlight Moment"),
    ("  05:10 Another Event  ", "05:10", "Another Event"),
    ("0:15 Short Clip", "0:15", "Short Clip"),
    ("10:00 - Description", "10:00", "- Description"),
    ("1:00:00 Start of Second Half", "1:00:00", "Start of Second Half"),
    ("59:59 End of First Half", "59:59", "End of First Half"),
    ("00:00 Kick-off", "00:00", "Kick-off"),
    ("12:34", "12:34", ""), # Timestamp only
    ("  45:01 ", "45:01", ""), # Timestamp only with spaces
])
def test_parse_description_line_valid(line, expected_timestamp, expected_text):
    """Tests parsing valid lines with timestamps and text."""
    timestamp, text = parse_description_line(line)
    assert timestamp == expected_timestamp
    assert text == expected_text.strip() # Assume text is stripped

@pytest.mark.parametrize("line", [
    "Just some text without a timestamp",
    "12345 Some numbers",
    "Not a time 1:2:3",
    "Time: 05:30", # Might be valid depending on exact spec, assume not for now
    "Another line",
    "1:23:45:67 Invalid format",
    "60:00 Invalid minutes",
    "00:60 Invalid seconds",
    "-01:00 Negative time",
])
def test_parse_description_line_invalid(line):
    """Tests lines that should not parse as valid timestamp lines."""
    assert parse_description_line(line) is None

# --- Test Timestamp Conversion ---

@pytest.mark.parametrize("timestamp_str, expected_seconds", [
    ("00:00", 0),
    ("00:45", 45),
    ("01:00", 60),
    ("01:30", 90),
    ("59:59", 3599),
    ("1:00:00", 3600),
    ("1:02:03", 3723),
    ("10:20:30", 37230),
    ("0:05", 5), # Handle single digit minute/hour if needed
    ("5:00", 300),
])
def test_convert_timestamp_to_seconds(timestamp_str, expected_seconds):
    """Tests converting MM:SS and H:MM:SS strings to total seconds."""
    assert convert_timestamp_to_seconds(timestamp_str) == expected_seconds

@pytest.mark.parametrize("invalid_timestamp", [
    "abc",
    "1:2:3:4",
    "1:60:00",
    "1:00:60",
    "1:",
    ":30",
    "-1:00",
])
def test_convert_timestamp_to_seconds_invalid(invalid_timestamp):
    """Tests invalid timestamp formats for conversion."""
    with pytest.raises(ValueError): # Assume it raises ValueError on bad format
        convert_timestamp_to_seconds(invalid_timestamp)

# --- Test Keyword Filtering ---

@pytest.fixture
def sample_timestamps():
    """Provides sample data for filtering tests."""
    return [
        ("00:10", "Goal Cardiff"),
        ("00:45", "Save Newport"),
        ("01:20", "Penalty Cardiff City"),
        ("02:00", "Foul Newport"),
        ("03:15", "Shot by Cardiff"),
        ("04:00", "Corner Newport"),
        ("05:05", "Goal CARDIFF"), # Test case insensitivity
    ]

def test_filter_timestamps_by_keywords_single(sample_timestamps):
    """Tests filtering with a single keyword (case-insensitive)."""
    keywords = ["Cardiff"]
    expected = [
        ("00:10", "Goal Cardiff"),
        ("01:20", "Penalty Cardiff City"),
        ("03:15", "Shot by Cardiff"),
        ("05:05", "Goal CARDIFF"),
    ]
    assert filter_timestamps_by_keywords(sample_timestamps, keywords) == expected

def test_filter_timestamps_by_keywords_multiple(sample_timestamps):
    """Tests filtering with multiple keywords."""
    keywords = ["Cardiff", "Newport"]
    # Expect all items back as they all contain either keyword
    assert filter_timestamps_by_keywords(sample_timestamps, keywords) == sample_timestamps

def test_filter_timestamps_by_keywords_specific(sample_timestamps):
    """Tests filtering with a more specific keyword."""
    keywords = ["Penalty"]
    expected = [
        ("01:20", "Penalty Cardiff City"),
    ]
    assert filter_timestamps_by_keywords(sample_timestamps, keywords) == expected

def test_filter_timestamps_by_keywords_no_match(sample_timestamps):
    """Tests filtering when no keywords match."""
    keywords = ["Bristol"]
    expected = []
    assert filter_timestamps_by_keywords(sample_timestamps, keywords) == expected

def test_filter_timestamps_by_keywords_empty_keywords(sample_timestamps):
    """Tests filtering with an empty keyword list (should return all)."""
    keywords = []
    assert filter_timestamps_by_keywords(sample_timestamps, keywords) == sample_timestamps

def test_filter_timestamps_by_keywords_empty_data():
    """Tests filtering with empty input data."""
    keywords = ["Cardiff"]
    assert filter_timestamps_by_keywords([], keywords) == []

# --- Test Filename Sanitization ---

@pytest.mark.parametrize("original, expected", [
    ("My Video Title", "My_Video_Title"),
    ("Video with spaces", "Video_with_spaces"),
    ("Special*Chars?<>:", "Special_Chars_"),
    ("Another/Example\\Path", "Another_Example_Path"),
    (" Dots... and Commas, ", "_Dots_and_Commas_"),
    ("Keep_Underscores", "Keep_Underscores"),
    ("Remove trailing/leading spaces ", "Remove_trailing_leading_spaces"),
    ("Numbers123 and Hyphens-", "Numbers123_and_Hyphens-"), # Assume hyphen is allowed
    ("!@#$%^&()=+[]{};'", "_____________"), # Replace many symbols
])
def test_sanitize_filename(original, expected):
    """Tests sanitizing strings for use as filenames."""
    assert sanitize_filename(original) == expected

def test_sanitize_filename_empty():
    """Tests sanitizing an empty string."""
    assert sanitize_filename("") == ""

def test_sanitize_filename_already_safe():
    """Tests sanitizing a string that is already safe."""
    assert sanitize_filename("already_safe_filename_123") == "already_safe_filename_123"