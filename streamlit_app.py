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
    st.sidebar.header("Settings")
    
    # Date range selector
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=datetime.now().date(),
            min_value=datetime.now().date(),
            max_value=datetime.now().date() + timedelta(days=180)
        )
    
    with col2:
        end_date = st.date_input(
            "End Date",
            value=datetime.now().date() + timedelta(days=7),
            min_value=datetime.now().date(),
            max_value=datetime.now().date() + timedelta(days=180)
        )
    
    # Threshold selector
    threshold = st.sidebar.slider(
        "Minimum Tide Height (m)",
        min_value=0.5,
        max_value=3.0,
        value=1.6,
        step=0.1
    )
    
    # Validate date range
    if start_date > end_date:
        st.error("Start date must be before end date!")
        return
    
    if (end_date - start_date).days > 30:
        st.warning("Large date ranges may take longer to load and display.")
    
    # Fetch and display data
    if st.sidebar.button("Generate Tide Chart", type="primary"):
        with st.spinner("Fetching tide data..."):
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.min.time())
            
            tide_data = get_tide_data(start_datetime, end_datetime)
            
            if tide_data:
                st.success(f"Fetched tide data for {(end_date - start_date).days + 1} days")
                
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