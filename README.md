# 🌊 Tide Predictor - Victoria Point Boat Ramp

An interactive tide prediction application for Victoria Point Boat Ramp (Masters Avenue, QLD) that helps boaters plan their trips by showing optimal boating windows based on tide levels and daylight hours.

## Features

- 📈 **Interactive Tide Charts** - Visualize tide levels with realistic sinusoidal interpolation
- 🟢 **Boatable Windows** - Green shaded areas indicate when tide is above your threshold during daylight hours
- 📊 **Daily Summary Table** - See useable window duration, start time, and end time for each day
- ⚙️ **Configurable Settings**:
  - Select custom date ranges (up to 180 days)
  - Adjust minimum tide height threshold (default: 1.6m)
- 🌅 **Daylight Hours** - Only shows boatable windows between 6:00 AM and 5:30 PM
- 📉 **Tide Statistics** - View max/min tide heights, total boatable hours, and best days

## Installation

### Prerequisites

- Python 3.13+ (or 3.8+)
- WillyWeather API key ([Get one here](https://www.willyweather.com.au/api/))

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/carlmalouf/BoatUsageTimes.git
   cd BoatUsageTimes
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   
   # On Windows
   .venv\Scripts\activate
   
   # On macOS/Linux
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure API Key**
   
   Copy the example environment file and add your API key:
   ```bash
   # On Windows
   copy .env.example .env
   
   # On macOS/Linux
   cp .env.example .env
   ```
   
   Edit `.env` and replace `your_api_key_here` with your WillyWeather API key:
   ```
   WILLY_WEATHER_API_KEY=your_actual_api_key_here
   ```

## Usage

### Run the Streamlit Web App

```bash
streamlit run streamlit_app.py
```

The app will open in your browser at `http://localhost:8501`

### Run the Command-Line Script

To generate a CSV file with tide predictions:

```bash
python main.py
```

This will create `tide_windows.csv` with 180 days of tide predictions.

## How It Works

### Tide Interpolation

The app uses **sinusoidal interpolation** between known tide points to create a more realistic representation of tide behavior:

- **Rising tides** (low → high): Uses negative cosine curve for natural acceleration
- **Falling tides** (high → low): Uses cosine curve for natural deceleration

This provides more accurate predictions than simple linear interpolation.

### Boatable Window Calculation

A time is considered "boatable" when:
1. Tide height is above the configured threshold (default: 1.6m)
2. Time is during daylight hours (6:00 AM - 5:30 PM)

The app calculates continuous windows for each day and displays:
- Total duration of the useable window
- Start time of the first boatable period
- End time of the last boatable period

## Configuration

### Location

Currently configured for:
- **Location**: Victoria Point Boat Ramp (Masters Avenue)
- **Region**: Brisbane, QLD
- **Coordinates**: -27.582, 153.3181
- **Location ID**: 33211 (WillyWeather)

To change the location, update the location ID in both `main.py` and `streamlit_app.py`:
```python
base_url = f"https://api.willyweather.com.au/v2/{API_KEY}/locations/{LOCATION_ID}/weather.json?forecasts=tides&startDate={start_date}&days={days}"
```

### Daylight Hours

Default daylight hours: 6:00 AM - 5:30 PM

To change, modify the time checks in the code:
```python
is_daylight = 6 <= time.hour < 17 or (time.hour == 17 and time.minute <= 30)
```

## Project Structure

```
BoatUsageTimes/
├── .env.example          # Template for environment variables
├── .gitignore           # Git ignore rules
├── requirements.txt     # Python dependencies
├── main.py             # Command-line script to generate CSV
├── streamlit_app.py    # Interactive web application
└── README.md           # This file
```

## API Information

This project uses the [WillyWeather API](https://www.willyweather.com.au/api/) for tide predictions.

- Free tier available with limitations
- Provides accurate tide data for Australian locations
- Includes high/low tide times and heights

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the MIT License.

## Acknowledgments

- Tide data provided by [WillyWeather API](https://www.willyweather.com.au/)
- Built with [Streamlit](https://streamlit.io/) and [Plotly](https://plotly.com/)
