import math
import threading
import time
from pathlib import Path

import joblib
import pandas as pd
import requests
from flask import Flask, jsonify, render_template, request


BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__)

model = joblib.load(BASE_DIR / "crop_model.pkl")

# TODO: Add API keys and model and city/country location
OPENWEATHER_API_KEY = "openweathermap api key"
GEMINI_API_KEY = "gemini api key"
GEMINI_MODEL = "gemini model"
CITY = "city"
COUNTRY_CODE = "country code"
WEATHER_REFRESH_SECONDS = 600
AI_REFRESH_SECONDS = 60

# Base sensor thresholds, adjust as needed
RAIN_WET_ADC_THRESHOLD = 2000
LIGHT_DARK_ADC_THRESHOLD = 3000
LIGHT_DIM_ADC_THRESHOLD = 1500
SOIL_WET_ADC_THRESHOLD = 1500
SOIL_DRY_ADC_THRESHOLD = 2800

state_lock = threading.Lock()
cached_weather = {
    "rainfall": 0.0,
    "aqi": 1,
    "owm_temp": 0.0,
    "owm_humidity": 0.0,
    "weather_status": "Waiting for weather update",
}

latest_sensor_data = {
    "sensor_temp": 0.0,
    "sensor_humidity": 0.0,
    "owm_temp": 0.0,
    "owm_humidity": 0.0,
    "rain_status": "WAITING",
    "rain_analog_raw": 0,
    "light_condition": "UNKNOWN",
    "ldr_raw": 0,
    "soil_status": "UNKNOWN",
    "soil_moisture_raw": 0,
    "ultrasonic_distance": 0.0,
    "harvest_status": "Waiting for sensor data",
    "rainfall": 0.0,
    "aqi": 1,
    "aqi_status": "Good",
    "weather_status": cached_weather["weather_status"],
    "recommended_crop": "Waiting for sensor data",
    "ai_recommendation": "AI advice will appear after sensor data is received",
    "ai_status": (
        "Not configured: add Gemini API key in app.py"
        if GEMINI_API_KEY == "PASTE_GEMINI_API_KEY_HERE"
        else "Waiting for sensor data"
    ),
}

ai_request_in_flight = False
last_ai_request_at = None


def get_latest_data():
    with state_lock:
        return latest_sensor_data.copy()


def _generate_ai_recommendation(sensor_data):
    prompt = (
        "You are an agriculture crop-options assistant. Use the weather and "
        "environment readings to suggest exactly 3 plausible crop options, ranked "
        "best fit first, with a very short reason for each. The scikit-learn crop "
        "prediction is only one reference point, not a restriction: freely suggest "
        "suitable crops outside its training labels. Do not just repeat the model "
        "prediction. Do not comment on, diagnose, or give advice about the hardware "
        "or sensors. If readings are explicitly marked uncalibrated, account for "
        "that uncertainty briefly without discussing hardware. Format as three "
        "numbered options, concise enough to read comfortably on the dashboard. No "
        "introduction or extra conclusion.\n\n"
        f"Sensor and weather data: {sensor_data}"
    )
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent",
        headers={"x-goog-api-key": GEMINI_API_KEY},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.6, "maxOutputTokens": 180},
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    candidates = payload.get("candidates", [])
    if not candidates:
        raise ValueError("Gemini returned no candidate")
    parts = candidates[0].get("content", {}).get("parts", [])
    recommendation = " ".join(
        part["text"].strip()
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ).strip()
    if not recommendation:
        raise ValueError("Gemini returned empty advice")
    return recommendation[:500]


def _run_ai_request(sensor_data):
    global ai_request_in_flight
    try:
        recommendation = _generate_ai_recommendation(sensor_data)
    except (
        requests.RequestException,
        AttributeError,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
    ) as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", "n/a")
        app.logger.warning(
            "Gemini recommendation request failed (%s, HTTP %s)",
            type(exc).__name__,
            status_code,
        )
        with state_lock:
            latest_sensor_data["ai_recommendation"] = "AI advice unavailable"
            latest_sensor_data["ai_status"] = "Failed; check Flask server log"
    else:
        with state_lock:
            latest_sensor_data["ai_recommendation"] = recommendation
            latest_sensor_data["ai_status"] = "Ready"
    finally:
        with state_lock:
            ai_request_in_flight = False


def _schedule_ai_request(sensor_data):
    global ai_request_in_flight, last_ai_request_at
    if not GEMINI_API_KEY or GEMINI_API_KEY == "PASTE_GEMINI_API_KEY_HERE":
        return

    now = time.monotonic()
    with state_lock:
        if ai_request_in_flight or (
            last_ai_request_at is not None
            and now - last_ai_request_at < AI_REFRESH_SECONDS
        ):
            return
        ai_request_in_flight = True
        last_ai_request_at = now
        latest_sensor_data["ai_status"] = "Generating advice"

    threading.Thread(
        target=_run_ai_request,
        args=(sensor_data,),
        daemon=True,
        name="gemini-recommendation",
    ).start()


def update_weather_cache_background():
    while True:
        if OPENWEATHER_API_KEY and OPENWEATHER_API_KEY != "PASTE_OPENWEATHER_API_KEY_HERE":
            try:
                weather_response = requests.get(
                    "https://api.openweathermap.org/data/2.5/weather",
                    params={
                        "q": f"{CITY},{COUNTRY_CODE}",
                        "appid": OPENWEATHER_API_KEY,
                        "units": "metric",
                    },
                    timeout=8,
                )
                weather_response.raise_for_status()
                weather_data = weather_response.json()

                rain_data = weather_data.get("rain") or {}
                rainfall = float(rain_data.get("1h", 0.0)) * 24
                owm_temp = float(weather_data["main"]["temp"])
                owm_humidity = float(weather_data["main"]["humidity"])
                latitude = float(weather_data["coord"]["lat"])
                longitude = float(weather_data["coord"]["lon"])

                aqi_response = requests.get(
                    "https://api.openweathermap.org/data/2.5/air_pollution",
                    params={
                        "lat": latitude,
                        "lon": longitude,
                        "appid": OPENWEATHER_API_KEY,
                    },
                    timeout=8,
                )
                aqi_response.raise_for_status()
                aqi_data = aqi_response.json()
                aqi_list = aqi_data.get("list", [])
                if not aqi_list:
                    raise ValueError("OpenWeather returned no air-quality data")
                aqi = int(aqi_list[0]["main"]["aqi"])
                if aqi not in range(1, 6):
                    raise ValueError("OpenWeather returned an invalid AQI")

                with state_lock:
                    cached_weather.update(
                        {
                            "rainfall": rainfall,
                            "aqi": aqi,
                            "owm_temp": owm_temp,
                            "owm_humidity": owm_humidity,
                            "weather_status": "OpenWeather data updated",
                        }
                    )
                    latest_sensor_data.update(cached_weather)
                    latest_sensor_data["aqi_status"] = {
                        1: "Good",
                        2: "Fair",
                        3: "Moderate",
                        4: "Poor",
                        5: "Very Poor",
                    }[aqi]
            except (
                requests.RequestException,
                AttributeError,
                KeyError,
                IndexError,
                TypeError,
                ValueError,
            ) as exc:
                status_code = getattr(getattr(exc, "response", None), "status_code", "n/a")
                app.logger.warning(
                    "OpenWeather update failed (%s, HTTP %s)",
                    type(exc).__name__,
                    status_code,
                )
                with state_lock:
                    cached_weather["weather_status"] = (
                        "OpenWeather update failed; check Flask server log"
                    )
                    latest_sensor_data["weather_status"] = cached_weather[
                        "weather_status"
                    ]
        else:
            with state_lock:
                cached_weather["weather_status"] = (
                    "Not configured: add OpenWeather API key in app.py"
                )
                latest_sensor_data["weather_status"] = cached_weather[
                    "weather_status"
                ]
        time.sleep(WEATHER_REFRESH_SECONDS)


@app.route("/api/sensor-data", methods=["POST"])
def receive_sensor_data():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"status": "error", "message": "Expected a JSON object"}), 400

    try:
        sensor_temp = float(data["temp"])
        sensor_humidity = float(data["humidity"])
        rain_analog_raw = int(data["rain_ao"])
        ldr_ao = int(data["ldr_ao"])
        soil_moisture_raw = int(data["soil_moisture"])
        ultrasonic_distance = float(data["distance"])
    except (KeyError, TypeError, ValueError):
        return jsonify(
            {
                "status": "error",
                "message": "Required sensor values are missing or invalid",
            }
        ), 400

    numeric_values = (
        sensor_temp,
        sensor_humidity,
        ultrasonic_distance,
    )
    if not all(math.isfinite(value) for value in numeric_values):
        return jsonify({"status": "error", "message": "Sensor values must be finite"}), 400
    if not 0 <= sensor_humidity <= 100:
        return jsonify({"status": "error", "message": "Humidity must be from 0 to 100"}), 400
    if not 0 <= rain_analog_raw <= 4095:
        return jsonify({"status": "error", "message": "rain_ao must be 0 to 4095"}), 400
    if not 0 <= ldr_ao <= 4095 or not 0 <= soil_moisture_raw <= 4095:
        return jsonify({"status": "error", "message": "Analog readings must be 0 to 4095"}), 400
    if not 0 <= ultrasonic_distance <= 400:
        return jsonify({"status": "error", "message": "Distance must be 0 to 400 cm"}), 400

    with state_lock:
        weather = cached_weather.copy()

    rain_status = "WET" if rain_analog_raw < RAIN_WET_ADC_THRESHOLD else "DRY"

    if ldr_ao >= LIGHT_DARK_ADC_THRESHOLD:
        light_condition = "DARK / SHADED"
    elif ldr_ao >= LIGHT_DIM_ADC_THRESHOLD:
        light_condition = "MODERATE / DIM"
    else:
        light_condition = "BRIGHT"

    if soil_moisture_raw == 0:
        soil_status = "NO SENSOR DETECTED"
    elif soil_moisture_raw < SOIL_WET_ADC_THRESHOLD:
        soil_status = "VERY WET / SATURATED"
    elif soil_moisture_raw < SOIL_DRY_ADC_THRESHOLD:
        soil_status = "MOIST / OPTIMAL"
    else:
        soil_status = "DRY / NEEDS WATER"

    harvest_status = (
        "READY TO HARVEST"
        if 0 < ultrasonic_distance < 20
        else "GROWING"
    )
    aqi = weather["aqi"]
    input_df = pd.DataFrame(
        [[sensor_temp, sensor_humidity, weather["rainfall"]]],
        columns=["temperature", "humidity", "rainfall"],
    )
    predicted_crop = str(model.predict(input_df)[0]).capitalize()

    with state_lock:
        latest_sensor_data.update(
            {
                "sensor_temp": sensor_temp,
                "sensor_humidity": sensor_humidity,
                "owm_temp": weather["owm_temp"],
                "owm_humidity": weather["owm_humidity"],
                "rain_status": rain_status,
                "rain_analog_raw": rain_analog_raw,
                "light_condition": light_condition,
                "ldr_raw": ldr_ao,
                "soil_status": soil_status,
                "soil_moisture_raw": soil_moisture_raw,
                "ultrasonic_distance": ultrasonic_distance,
                "harvest_status": harvest_status,
                "rainfall": weather["rainfall"],
                "aqi": aqi,
                "aqi_status": {
                    1: "Good",
                    2: "Fair",
                    3: "Moderate",
                    4: "Poor",
                    5: "Very Poor",
                }.get(aqi, "Unknown"),
                "weather_status": weather["weather_status"],
                "recommended_crop": predicted_crop,
            }
        )
        ai_input = {
            key: latest_sensor_data[key]
            for key in (
                "sensor_temp",
                "sensor_humidity",
                "owm_temp",
                "owm_humidity",
                "rain_status",
                "rain_analog_raw",
                "light_condition",
                "ldr_raw",
                "soil_status",
                "soil_moisture_raw",
                "ultrasonic_distance",
                "harvest_status",
                "rainfall",
                "aqi",
                "aqi_status",
                "weather_status",
                "recommended_crop",
            )
        }

    _schedule_ai_request(ai_input)
    return jsonify({"status": "success", **get_latest_data()}), 200


@app.route("/api/get-data", methods=["GET"])
def get_sensor_data():
    return jsonify(get_latest_data())


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", data=get_latest_data())


if __name__ == "__main__":
    threading.Thread(
        target=update_weather_cache_background,
        daemon=True,
        name="openweather-updater",
    ).start()
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
