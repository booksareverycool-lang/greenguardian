# GreenGuardian

GreenGuardian is an IoT crop-monitoring application that combines ESP32 sensor readings, local weather data, machine-learning predictions, and AI-generated crop suggestions in a web dashboard.

## System overview

1. An ESP32 reads a DHT11 temperature and humidity sensor, rain and light sensors, a soil-moisture sensor, and an ultrasonic distance sensor.
2. The ESP32 sends readings over Wi-Fi to a Flask server on the same local network.
3. The server retrieves weather information from OpenWeatherMap, classifies sensor conditions, and uses a scikit-learn model to predict a crop.
4. The server can request three additional crop suggestions from Gemini. These suggestions are presented separately from the model prediction.
5. A browser dashboard displays sensor readings, weather, and crop recommendations. The ESP32 also reports connection and response details through its Serial Monitor.

The crop model uses temperature, humidity, and rainfall as input features. Rainfall is estimated by multiplying the current OpenWeatherMap one-hour precipitation value by 24; it is not a measured daily total. Sensor cutoff values are initial estimates and may need adjustment for the specific sensor modules.

## Requirements

- Windows computer running Python 3
- Arduino IDE with ESP32 board support
- ESP32 development board and compatible sensors
- OpenWeather API key for weather data
- Gemini API key for AI-generated suggestions
- A Wi-Fi network shared by the ESP32 and the computer running Flask

## Run the Flask server

### 1. Obtain the project files

Clone the repository or download and extract its contents. Preserve the project structure, including `templates/index.html`, `crop_model.pkl`, and `ESP32_Client/ESP32_Client.ino`.

### 2. Install Python dependencies

Open PowerShell in the project directory and create a virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 3. Configure the server

Set `OPENWEATHER_API_KEY`, `GEMINI_API_KEY`, `CITY`, and `COUNTRY_CODE` in `app.py`. API keys should be configured locally and must not be committed to a public repository.

The supplied `crop_model.pkl` is loaded by the server. Model retraining is optional; if `Crop_recommendation.csv` is available, run the following from the project directory:

```powershell
python train_model.py
```

### 4. Start the server

From the activated virtual environment, run:

```powershell
python app.py
```

Keep the terminal open while the system is in use. The server listens on port `5000`. Open the dashboard on the server computer at:

```text
http://127.0.0.1:5000
```

The live sensor data endpoint is available at `http://127.0.0.1:5000/api/get-data`. OpenWeather data refreshes every 10 minutes, and Gemini requests are made in the background no more than once per minute. If Gemini is unavailable, the dashboard can still show the machine-learning prediction.

## Configure and upload the ESP32 sketch

### 1. Install Arduino libraries

In Arduino IDE's Library Manager, install:

- **ArduinoJson** by Benoit Blanchon
- **DHT sensor library** by Adafruit
- **Adafruit Unified Sensor** by Adafruit

Install the ESP32 board support package if it is not already installed.

### 2. Configure network settings

Open `ESP32_Client/ESP32_Client.ino` and set the Wi-Fi network name and password. Find the server computer's IPv4 address with `ipconfig`, then set `serverUrl` to that address using port `5000` and the `/api/sensor-data` path. For example:

```text
http://192.168.1.25:5000/api/sensor-data
```

Use the current IPv4 address of the server computer; it can change when the computer connects to a different network. Do not use `127.0.0.1` in the ESP32 URL. The ESP32 and server computer must be able to communicate on the same local network. A 2.4 GHz Wi-Fi network is recommended. If connections are blocked, allow Python through Windows Firewall for the private network.

### 3. Check wiring

The sketch's example GPIO assignments are:

| Component                          | Example ESP32 GPIO |
| ---------------------------------- | -----------------: |
| DHT11 data                         |                 32 |
| Rain sensor analog output (AO)     |                 34 |
| LDR analog output                  |                 36 |
| Soil-moisture sensor analog output |                 35 |
| Ultrasonic TRIG                    |                  5 |
| Ultrasonic ECHO                    |                 18 |

Update the sketch pin definitions to match the actual wiring. ESP32 GPIO inputs are not 5 V tolerant. If a 5 V-powered HC-SR04 is used, place a voltage divider or level shifter on ECHO. Verify sensor supply voltage and pinout, connect sensor grounds to ESP32 ground, and keep all ESP32 input signals at or below 3.3 V. A bare DHT11 may require a pull-up resistor from DATA to 3.3 V; many breakout boards include one.

### 4. Upload and verify

Select the correct ESP32 board and COM port in Arduino IDE, then upload the sketch. Open Serial Monitor at **115200 baud**. The sketch sends readings approximately every five seconds; successful posts receive an HTTP `200` response. Check the dashboard or `/api/get-data` endpoint to confirm that sensor values are updating.

The ESP32 needs power, Wi-Fi access, and a reachable Flask server to send readings. USB is only required for programming and Serial Monitor access if another suitable power source is used.

## Sensor thresholds

The rain, light, and soil sensors send raw 12-bit ADC values (0–4095). The Flask server currently applies these initial thresholds:

| Sensor        | Interpretation                                                      |
| ------------- | ------------------------------------------------------------------- |
| Rain          | ADC below 2000: wet; otherwise dry                                  |
| Light         | ADC at or above 3000: dark; at or above 1500: dim; otherwise bright |
| Soil moisture | ADC below 1500: very wet; below 2800: moist; otherwise dry          |

These values are starting estimates, not calibrated measurements. Adjust the corresponding constants near the top of `app.py` after observing readings from the installed sensor modules.

## Dataset attribution

The crop recommendation model is based on the [Crop Recommendation Dataset](https://www.kaggle.com/datasets/atharvaingle/crop-recommendation-dataset) by **Atharva Ingle**, obtained from Kaggle. The Kaggle listing identifies the dataset as licensed under the **Apache License 2.0**.

The project dataset was modified by removing the `N`, `P`, `K`, and `ph` columns. The remaining dataset is used to train the crop recommendation model.

The dataset's license applies to the dataset and its derivatives, not automatically to GreenGuardian's source code. If redistributing the dataset, include the Apache License 2.0 text and retain the required copyright and license notices. Refer to the Kaggle source for the original dataset and license details.
