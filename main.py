import requests
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import csv
import math
from typing import List, Tuple, Dict

# Load API key from environment variables
load_dotenv()
API_KEY = os.getenv('WILLY_WEATHER_API_KEY')

def get_tide_data(days=2):
    # Use current date as start date
    start_date = datetime.now().strftime("%Y-%m-%d")
    base_url = f"https://api.willyweather.com.au/v2/OTJlZTE3YTZlMDZhOTk1OWE5ZGZlM2/locations/33211/weather.json?forecasts=tides&startDate={start_date}&days={days}"
    
    try:
        response = requests.get(base_url)
        
        if response.status_code != 200:
            print(f"API Response: {response.text}")
            response.raise_for_status()
            
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return None

def interpolate_tide_height(time: datetime, prev_tide: Dict, next_tide: Dict) -> float:
    """Sinusoidal interpolation of tide height between two known tide points."""
    import math
    
    prev_time = datetime.strptime(prev_tide['dateTime'], "%Y-%m-%d %H:%M:%S")
    next_time = datetime.strptime(next_tide['dateTime'], "%Y-%m-%d %H:%M:%S")
    
    # Calculate time proportion between tides
    total_seconds = (next_time - prev_time).total_seconds()
    elapsed_seconds = (time - prev_time).total_seconds()
    proportion = elapsed_seconds / total_seconds
    
    # Determine the phase based on tide types
    prev_type = prev_tide['type']
    next_type = next_tide['type']
    
    # Use sinusoidal interpolation based on tide progression
    if prev_type == 'high' and next_type == 'low':
        # Falling tide: cosine curve from peak (1) to trough (0)
        phase = math.cos(proportion * math.pi)
        # Map from [1, -1] to [prev_height, next_height]
        phase_normalized = (phase + 1) / 2  # Now [0, 1] where 1 is prev, 0 is next
    elif prev_type == 'low' and next_type == 'high':
        # Rising tide: negative cosine curve from trough to peak
        phase = -math.cos(proportion * math.pi)
        # Map from [-1, 1] to [prev_height, next_height]
        phase_normalized = (phase + 1) / 2  # Now [0, 1] where 0 is prev, 1 is next
    else:
        # Same type transitions (rare) - use smoother sinusoidal interpolation
        phase = math.sin(proportion * math.pi / 2)
        phase_normalized = phase
    
    # Calculate height using sinusoidal interpolation
    height_diff = next_tide['height'] - prev_tide['height']
    
    if prev_type == 'high' and next_type == 'low':
        # Falling tide
        return prev_tide['height'] - (prev_tide['height'] - next_tide['height']) * (1 - phase_normalized)
    elif prev_type == 'low' and next_type == 'high':
        # Rising tide  
        return prev_tide['height'] + height_diff * phase_normalized
    else:
        # Fallback to smooth interpolation
        return prev_tide['height'] + height_diff * phase_normalized

def find_tide_windows(tides: List[Dict], threshold: float = 1.6) -> Dict[str, List[Tuple[datetime, datetime, str]]]:
    """Find windows where tide is above threshold during daylight hours."""
    windows = {}
    
    # Convert tides list to easier format and sort by date
    tide_points = [(datetime.strptime(t['dateTime'], "%Y-%m-%d %H:%M:%S"), t) for t in tides]
    tide_points.sort()
    
    # Track current window state
    current_window_start = None
    previous_date = None
    
    for i in range(len(tide_points) - 1):
        prev_tide_time, prev_tide = tide_points[i]
        next_tide_time, next_tide = tide_points[i + 1]
        
        # Check each 15-minute interval between these tides
        current_time = prev_tide_time
        
        while current_time <= next_tide_time:
            date_str = current_time.strftime("%Y-%m-%d")
            
            # If we've moved to a new day, close any open window from previous day
            if previous_date is not None and date_str != previous_date and current_window_start is not None:
                # Close window at end of previous day (5:30 PM)
                end_of_day = datetime.combine(current_window_start.date(), datetime.min.time().replace(hour=17, minute=30))
                duration = end_of_day - current_window_start
                duration_str = f"{int(duration.total_seconds() // 3600):02d}:{int((duration.total_seconds() % 3600) // 60):02d}"
                
                if previous_date not in windows:
                    windows[previous_date] = []
                windows[previous_date].append((current_window_start, end_of_day, duration_str))
                current_window_start = None
            
            previous_date = date_str
            
            # Only consider daylight hours (6:00 AM to 5:30 PM)
            is_daylight = 6 <= current_time.hour < 17 or (current_time.hour == 17 and current_time.minute <= 30)
            
            if is_daylight:
                height = interpolate_tide_height(current_time, prev_tide, next_tide)
                
                # Check if we should start a new window
                if height >= threshold and current_window_start is None:
                    current_window_start = current_time
                
                # Check if we should end the current window
                elif height < threshold and current_window_start is not None:
                    # End the current window
                    duration = current_time - current_window_start
                    duration_str = f"{int(duration.total_seconds() // 3600):02d}:{int((duration.total_seconds() % 3600) // 60):02d}"
                    
                    if date_str not in windows:
                        windows[date_str] = []
                    windows[date_str].append((current_window_start, current_time, duration_str))
                    current_window_start = None
            
            # If we're outside daylight hours and have an open window, close it
            elif not is_daylight and current_window_start is not None:
                # Close window at end of daylight (5:30 PM)
                end_of_daylight = datetime.combine(current_time.date(), datetime.min.time().replace(hour=17, minute=30))
                if current_window_start <= end_of_daylight:
                    duration = end_of_daylight - current_window_start
                    duration_str = f"{int(duration.total_seconds() // 3600):02d}:{int((duration.total_seconds() % 3600) // 60):02d}"
                    
                    if date_str not in windows:
                        windows[date_str] = []
                    windows[date_str].append((current_window_start, end_of_daylight, duration_str))
                current_window_start = None
            
            current_time += timedelta(minutes=15)
    
    # Close any remaining open window
    if current_window_start is not None and previous_date is not None:
        end_time = datetime.combine(current_window_start.date(), datetime.min.time().replace(hour=17, minute=30))
        if current_window_start <= end_time:
            duration = end_time - current_window_start
            duration_str = f"{int(duration.total_seconds() // 3600):02d}:{int((duration.total_seconds() % 3600) // 60):02d}"
            
            if previous_date not in windows:
                windows[previous_date] = []
            windows[previous_date].append((current_window_start, end_time, duration_str))
    
    return windows

def write_tide_windows_to_csv(windows: Dict[str, List[Tuple[datetime, datetime, str]]], filename: str = 'tide_windows.csv'):
    """Write tide windows to CSV file."""
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Date', 'Window 1', 'Duration 1', 'Window 2', 'Duration 2'])
        
        for date in sorted(windows.keys()):
            day_windows = windows[date]
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%A, %B %d")
            
            row = [formatted_date]
            
            # Add up to 2 windows for the day
            for i in range(min(len(day_windows), 2)):
                start_time = day_windows[i][0].strftime("%I:%M %p")
                end_time = day_windows[i][1].strftime("%I:%M %p")
                duration = day_windows[i][2]
                row.extend([f"{start_time} - {end_time}", duration])
            
            # Fill empty slots if less than 2 windows
            while len(row) < 5:
                row.extend(['', ''])
            
            writer.writerow(row)

def main():
    print("Fetching tide data for Victoria Point Boat Ramp...")
    tide_data = get_tide_data(days=180)
    
    if tide_data:
        # Extract tide entries from the correct API structure
        tide_days = tide_data['forecasts']['tides']['days']
        
        # Flatten all tide entries from all days into a single list
        tides = []
        for day in tide_days:
            tides.extend(day['entries'])
        
        windows = find_tide_windows(tides, threshold=1.6)
        write_tide_windows_to_csv(windows)
        print("\nTide windows have been written to tide_windows.csv")
    else:
        print("Failed to fetch tide data")

if __name__ == "__main__":
    main()