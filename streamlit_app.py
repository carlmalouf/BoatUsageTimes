import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import math
from datetime import datetime, timedelta
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_tide_data(start_date, end_date):
    """Fetch tide data from WillyWeather API for date range"""
    start_date_str = start_date.strftime("%Y-%m-%d")
    days = (end_date - start_date).days + 1
    
    base_url = f"https://api.willyweather.com.au/v2/OTJlZTE3YTZlMDZhOTk1OWE5ZGZlM2/locations/33211/weather.json?forecasts=tides&startDate={start_date_str}&days={days}"
    
    try:
        response = requests.get(base_url)
        if response.status_code != 200:
            st.error(f"API Error: {response.status_code}")
            return None
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data: {e}")
        return None

def interpolate_tide_height(time: datetime, prev_tide: dict, next_tide: dict) -> float:
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

def create_tide_chart(tide_data, start_date, end_date, threshold=1.6):
    """Create a Plotly chart showing tide levels with shaded areas"""
    
    # Extract tide entries
    tide_days = tide_data['forecasts']['tides']['days']
    tides = []
    for day in tide_days:
        tides.extend(day['entries'])
    
    # Convert to datetime objects and sort
    tide_points = [(datetime.strptime(t['dateTime'], "%Y-%m-%d %H:%M:%S"), t) for t in tides]
    tide_points.sort()
    
    # Create interpolated data points every 15 minutes
    all_times = []
    all_heights = []
    
    current_time = start_date
    end_time = end_date + timedelta(days=1)
    
    while current_time <= end_time:
        # Find surrounding tide points
        prev_tide = None
        next_tide = None
        
        for i, (tide_time, tide_data) in enumerate(tide_points):
            if tide_time <= current_time:
                prev_tide = (tide_time, tide_data)
            elif tide_time > current_time and next_tide is None:
                next_tide = (tide_time, tide_data)
                break
        
        if prev_tide and next_tide:
            height = interpolate_tide_height(current_time, prev_tide[1], next_tide[1])
            all_times.append(current_time)
            all_heights.append(height)
        
        current_time += timedelta(minutes=15)
    
    # Create the main tide chart
    fig = go.Figure()
    
    # Add tide level line
    fig.add_trace(go.Scatter(
        x=all_times,
        y=all_heights,
        mode='lines',
        name='Tide Level',
        line=dict(color='blue', width=2)
    ))
    
    # Add threshold line
    fig.add_hline(
        y=threshold,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Threshold ({threshold}m)"
    )
    
    # Add shaded areas for boatable conditions (above threshold + daylight)
    for i in range(len(all_times)):
        time = all_times[i]
        height = all_heights[i]
        
        # Check if it's daylight hours (6:00 AM to 5:30 PM)
        is_daylight = 6 <= time.hour < 17 or (time.hour == 17 and time.minute <= 30)
        
        if height >= threshold and is_daylight:
            # Find the start and end of this boatable period
            start_idx = i
            end_idx = i
            
            # Find the end of this period
            while (end_idx < len(all_times) - 1 and 
                   all_heights[end_idx + 1] >= threshold and
                   (6 <= all_times[end_idx + 1].hour < 17 or 
                    (all_times[end_idx + 1].hour == 17 and all_times[end_idx + 1].minute <= 30))):
                end_idx += 1
            
            # Add shaded area for this boatable period
            fig.add_shape(
                type="rect",
                x0=all_times[start_idx],
                x1=all_times[end_idx],
                y0=0,
                y1=max(all_heights) * 1.1,
                fillcolor="rgba(0, 255, 0, 0.2)",
                line=dict(width=0),
            )
    
    # Add actual tide points
    tide_times = [t[0] for t in tide_points if start_date <= t[0] <= end_date + timedelta(days=1)]
    tide_heights = [t[1]['height'] for t in tide_points if start_date <= t[0] <= end_date + timedelta(days=1)]
    tide_types = [t[1]['type'] for t in tide_points if start_date <= t[0] <= end_date + timedelta(days=1)]
    
    colors = ['red' if t == 'high' else 'blue' for t in tide_types]
    
    fig.add_trace(go.Scatter(
        x=tide_times,
        y=tide_heights,
        mode='markers',
        name='Tide Points',
        marker=dict(color=colors, size=8),
        text=[f"{t.capitalize()} Tide<br>{h:.2f}m" for t, h in zip(tide_types, tide_heights)],
        hovertemplate='%{text}<br>%{x}<extra></extra>'
    ))
    
    # Update layout
    fig.update_layout(
        title="Tide Levels and Boatable Windows",
        xaxis_title="Date/Time",
        yaxis_title="Tide Height (m)",
        hovermode='x unified',
        showlegend=True,
        height=600
    )
    
    return fig

def main():
    st.set_page_config(page_title="Tide Predictor", page_icon="🌊", layout="wide")
    
    st.title("🌊 Tide Predictor - Victoria Point Boat Ramp")
    st.markdown("**Interactive tide prediction with boatable windows (tide > 1.6m during daylight hours)**")
    
    # Sidebar for controls
    st.sidebar.header("⚙️ Settings")
    
    st.sidebar.markdown("### 📅 Date Range")
    st.sidebar.info("Select the date range to fetch tide predictions from the API")
    
    # Date range selector
    start_date = st.sidebar.date_input(
        "From Date",
        value=datetime.now().date(),
        min_value=datetime.now().date(),
        max_value=datetime.now().date() + timedelta(days=180),
        help="Start date for tide predictions"
    )
    
    end_date = st.sidebar.date_input(
        "To Date",
        value=datetime.now().date() + timedelta(days=7),
        min_value=datetime.now().date(),
        max_value=datetime.now().date() + timedelta(days=180),
        help="End date for tide predictions"
    )
    
    # Threshold selector
    st.sidebar.markdown("### 🌊 Tide Settings")
    threshold = st.sidebar.slider(
        "Minimum Tide Height (m)",
        min_value=0.5,
        max_value=3.0,
        value=1.6,
        step=0.1,
        help="Minimum tide height required for boating"
    )
    
    # Validate date range
    if start_date > end_date:
        st.error("❌ Start date must be before end date!")
        return
    
    days_selected = (end_date - start_date).days + 1
    if days_selected > 30:
        st.sidebar.warning(f"⚠️ Large date range ({days_selected} days) may take longer to load")
    else:
        st.sidebar.success(f"✅ Fetching {days_selected} days of tide data")
    
    # Fetch and display data
    if st.sidebar.button("🔄 Fetch Tide Data", type="primary", use_container_width=True):
        with st.spinner("Fetching tide data..."):
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.min.time())
            
            tide_data = get_tide_data(start_datetime, end_datetime)
            
            if tide_data:
                st.success(f"✅ Successfully fetched tide data from {start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')} ({days_selected} days)")
                
                # Create and display chart
                fig = create_tide_chart(tide_data, start_datetime, end_datetime, threshold)
                st.plotly_chart(fig, use_container_width=True)
                
                # Display some statistics
                col1, col2, col3 = st.columns(3)
                
                # Extract tide entries for statistics
                tide_days = tide_data['forecasts']['tides']['days']
                all_tides = []
                for day in tide_days:
                    all_tides.extend(day['entries'])
                
                with col1:
                    st.metric("Total Tide Points", len(all_tides))
                
                with col2:
                    heights = [t['height'] for t in all_tides]
                    st.metric("Max Tide Height", f"{max(heights):.2f}m")
                
                with col3:
                    st.metric("Min Tide Height", f"{min(heights):.2f}m")
                
                # Calculate useable windows for each day
                st.markdown("---")
                st.subheader("📊 Daily Boatable Hours")
                st.markdown(f"Days with tide above **{threshold}m** during daylight hours (6:00 AM - 5:30 PM)")
                
                # Convert tides list and sort
                tide_points = [(datetime.strptime(t['dateTime'], "%Y-%m-%d %H:%M:%S"), t) for t in all_tides]
                tide_points.sort()
                
                # Calculate useable windows per day (start time, end time)
                daily_windows = {}
                current_window_start = None
                previous_date = None
                
                for i in range(len(tide_points) - 1):
                    prev_tide_time, prev_tide = tide_points[i]
                    next_tide_time, next_tide = tide_points[i + 1]
                    
                    current_time = prev_tide_time
                    
                    while current_time <= next_tide_time:
                        date_str = current_time.strftime("%Y-%m-%d")
                        
                        # If we've moved to a new day, close any open window from previous day
                        if previous_date is not None and date_str != previous_date and current_window_start is not None:
                            end_of_day = datetime.combine(current_window_start.date(), datetime.min.time().replace(hour=17, minute=30))
                            if previous_date not in daily_windows:
                                daily_windows[previous_date] = []
                            daily_windows[previous_date].append((current_window_start, end_of_day))
                            current_window_start = None
                        
                        previous_date = date_str
                        
                        # Only consider daylight hours
                        is_daylight = 6 <= current_time.hour < 17 or (current_time.hour == 17 and current_time.minute <= 30)
                        
                        if is_daylight:
                            height = interpolate_tide_height(current_time, prev_tide, next_tide)
                            
                            # Check if we should start a new window
                            if height >= threshold and current_window_start is None:
                                current_window_start = current_time
                            
                            # Check if we should end the current window
                            elif height < threshold and current_window_start is not None:
                                if date_str not in daily_windows:
                                    daily_windows[date_str] = []
                                daily_windows[date_str].append((current_window_start, current_time))
                                current_window_start = None
                        
                        # If we're outside daylight hours and have an open window, close it
                        elif not is_daylight and current_window_start is not None:
                            end_of_daylight = datetime.combine(current_time.date(), datetime.min.time().replace(hour=17, minute=30))
                            if current_window_start <= end_of_daylight:
                                if date_str not in daily_windows:
                                    daily_windows[date_str] = []
                                daily_windows[date_str].append((current_window_start, end_of_daylight))
                            current_window_start = None
                        
                        current_time += timedelta(minutes=15)
                
                # Close any remaining open window
                if current_window_start is not None and previous_date is not None:
                    end_time = datetime.combine(current_window_start.date(), datetime.min.time().replace(hour=17, minute=30))
                    if current_window_start <= end_time:
                        if previous_date not in daily_windows:
                            daily_windows[previous_date] = []
                        daily_windows[previous_date].append((current_window_start, end_time))
                
                # Create DataFrame for table
                table_data = []
                for date_str in sorted(daily_windows.keys()):
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    formatted_date = date_obj.strftime("%A, %B %d, %Y")
                    windows = daily_windows[date_str]
                    
                    if windows:
                        # Combine all windows for the day
                        total_minutes = sum((end - start).total_seconds() / 60 for start, end in windows)
                        hours = total_minutes / 60
                        
                        # Format duration as HH:MM
                        hours_int = int(hours)
                        minutes_int = int((hours - hours_int) * 60)
                        duration_formatted = f"{hours_int}h {minutes_int:02d}m"
                        
                        # Get first window start and last window end
                        first_start = min(windows, key=lambda x: x[0])[0]
                        last_end = max(windows, key=lambda x: x[1])[1]
                        
                        table_data.append({
                            "Date": formatted_date,
                            "Useable Window": duration_formatted,
                            "Start Time": first_start.strftime("%I:%M %p"),
                            "End Time": last_end.strftime("%I:%M %p")
                        })
                    else:
                        table_data.append({
                            "Date": formatted_date,
                            "Useable Window": "0h 00m",
                            "Start Time": "-",
                            "End Time": "-"
                        })
                
                df = pd.DataFrame(table_data)
                
                # Display table
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Date": st.column_config.TextColumn("Date", width="large"),
                        "Useable Window": st.column_config.TextColumn("Duration", width="medium"),
                        "Start Time": st.column_config.TextColumn("Start Time", width="medium"),
                        "End Time": st.column_config.TextColumn("End Time", width="medium")
                    }
                )
                
                # Summary statistics
                total_minutes = 0
                for windows in daily_windows.values():
                    for start, end in windows:
                        total_minutes += (end - start).total_seconds() / 60
                
                total_boatable_hours = total_minutes / 60
                avg_hours_per_day = total_boatable_hours / len(daily_windows) if daily_windows else 0
                
                # Find best day
                best_day = None
                best_hours = 0
                for date_str, windows in daily_windows.items():
                    day_minutes = sum((end - start).total_seconds() / 60 for start, end in windows)
                    if day_minutes > best_hours * 60:
                        best_hours = day_minutes / 60
                        best_day = date_str
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Boatable Hours", f"{total_boatable_hours:.1f}h")
                with col2:
                    st.metric("Average Hours/Day", f"{avg_hours_per_day:.1f}h")
                with col3:
                    if best_day:
                        best_date = datetime.strptime(best_day, "%Y-%m-%d").strftime("%b %d")
                        st.metric("Best Day", f"{best_date} ({best_hours:.1f}h)")
                
            else:
                st.error("Failed to fetch tide data. Please check your API connection.")
    
    # Information section
    with st.expander("ℹ️ About This App"):
        st.markdown("""
        This app provides tide predictions for **Victoria Point Boat Ramp** with visual indicators for optimal boating conditions.
        
        **Features:**
        - 📈 Interactive tide level chart with **realistic sinusoidal interpolation** between tide points
        - 🟢 **Green shaded areas** indicate boatable windows (tide > threshold during daylight hours 6:00 AM - 5:30 PM)
        - 🔴 Red dots: High tides
        - 🔵 Blue dots: Low tides
        - 📊 Adjustable tide height threshold
        - 📅 Flexible date range selection (up to 180 days)
        - 🌊 **Sinusoidal tide modeling** for more accurate representation of tide behavior
        
        **Boatable Conditions:**
        - Tide height must be above the selected threshold (default 1.6m)
        - Must be during daylight hours (6:00 AM to 5:30 PM)
        
        **Data Source:** WillyWeather API for Victoria Point Boat Ramp (Masters Avenue)
        """)

if __name__ == "__main__":
    main()