#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <DHT.h>

// TODO: Add your Wi-Fi credentials 
// Note: Only 2.4 GHz networks will work with the ESP32, 5 GHz networks are not supported.
const char* ssid     = "ssid";
const char* password = "password";

// TODO: Change to your computer's IP address  (replace w, x, y and z with the actual values)
const char* serverUrl = "http://w.x.y.z:5000/api/sensor-data";

// TODO: Change to your sensor pins' GPIO numbers
#define DHTPIN        32      
#define DHTTYPE       DHT11   
#define RAIN_AO_PIN   34      
#define LDR_AO_PIN    36      
#define SOIL_AO_PIN   35      
#define TRIG_PIN      5       
#define ECHO_PIN      18      

DHT dht(DHTPIN, DHTTYPE);

void setup() {
  Serial.begin(115200);
  delay(1000);

  dht.begin();
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  analogReadResolution(12);

  Serial.println();
  Serial.print("Connecting to Wi-Fi: ");
  Serial.println(ssid);
  WiFi.setAutoReconnect(true);
  WiFi.begin(ssid, password);

  unsigned long wifiStart = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - wifiStart < 15000) {
    delay(500);
    Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connected successfully!");
    Serial.print("ESP32 IP Address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nWiFi not connected; check SSID/password.");
  }
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi disconnected; retrying...");
    WiFi.reconnect();
    delay(2000);
    return;
  }

  float humidity = dht.readHumidity();
  float temp = dht.readTemperature();
  if (isnan(humidity) || isnan(temp)) {
    Serial.println("DHT11 read failed; check its wiring and pull-up.");
    delay(2000);
    return;
  }

  int rain_ao = analogRead(RAIN_AO_PIN);
  int ldr_ao = analogRead(LDR_AO_PIN);
  int soil_moisture = analogRead(SOIL_AO_PIN);

  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  long duration = pulseIn(ECHO_PIN, HIGH, 30000);
  float distanceCm = duration * 0.0343 / 2.0;
  if (distanceCm > 400 || distanceCm <= 0) {
    distanceCm = 0.0;
  }

  StaticJsonDocument<256> payload;
  payload["temp"] = temp;
  payload["humidity"] = humidity;
  payload["rain_ao"] = rain_ao;
  payload["ldr_ao"] = ldr_ao;
  payload["soil_moisture"] = soil_moisture;
  payload["distance"] = distanceCm;

  String jsonPayload;
  serializeJson(payload, jsonPayload);

  HTTPClient http;
  if (!http.begin(serverUrl)) {
    Serial.println("Could not start HTTP connection.");
    delay(5000);
    return;
  }
  http.setTimeout(25000);
  http.addHeader("Content-Type", "application/json");

  int httpResponseCode = http.POST(jsonPayload);
  if (httpResponseCode > 0) {
    String response = http.getString();
    Serial.printf("HTTP %d: %s\n", httpResponseCode, response.c_str());
    if (httpResponseCode == HTTP_CODE_OK) {
      DynamicJsonDocument result(2048);
      DeserializationError error = deserializeJson(result, response);
      if (error) {
        Serial.printf("Response JSON parse failed: %s\n", error.c_str());
      } else {
        Serial.printf("Model crop: %s\n", result["recommended_crop"] | "Unavailable");
        Serial.printf("Gemini (%s): %s\n",
                      result["ai_status"] | "unknown",
                      result["ai_recommendation"] | "Unavailable");
      }
    } else {
      Serial.printf("Server returned HTTP %d: %s\n", httpResponseCode, response.c_str());
    }
  } else {
    Serial.printf("HTTP error: %s\n", http.errorToString(httpResponseCode).c_str());
  }

  http.end();
  delay(5000);
}
