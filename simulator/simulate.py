import json
import os
import random
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

MQTT_BROKER_HOST = os.environ.get("MQTT_BROKER_HOST", "mosquitto")
MQTT_BROKER_PORT = int(os.environ.get("MQTT_BROKER_PORT", "1883"))
MQTT_USERNAME = os.environ.get("MQTT_USERNAME", "")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD", "")
MQTT_TOPIC_PREFIX = os.environ.get("MQTT_TOPIC_PREFIX", "ecs")
PUBLISH_INTERVAL_SECONDS = float(os.environ.get("SIMULATOR_INTERVAL_SECONDS", "3"))


def parse_device_tokens(raw):
    """Parses SIMULATOR_DEVICE_TOKENS="slug1:token1,slug2:token2" into a dict."""
    tokens = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair or ":" not in pair:
            continue
        slug, token = pair.split(":", 1)
        tokens[slug.strip()] = token.strip()
    return tokens


DEVICE_TOKENS = parse_device_tokens(os.environ.get("SIMULATOR_DEVICE_TOKENS", ""))

# variable -> (min, max, normal value, noise per tick, alert threshold)
# Los umbrales deben coincidir con el "Umbral de alerta" de cada gadget en el dashboard
# (y, con hardware real, con los que use Node-RED/PLC).
VARIABLE_RANGES = {
    "ch4": (0.0, 300.0, 20.0, 8.0, 100.0),       # ppm
    "co2": (400.0, 3000.0, 700.0, 60.0, 1000.0), # ppm
    "pm10": (5.0, 250.0, 35.0, 6.0, 50.0),       # µg/m³
}

# device_slug -> variable it reports (un ESP32 por sensor)
SENSOR_DEVICES = {
    "esp32-ch4": "ch4",
    "esp32-co2": "co2",
    "esp32-pm10": "pm10",
}

# Variador de frecuencia (VDF) comandado por el PLC, publicado como un dispositivo más.
PLC_DEVICE = "plc-ventilador"
# sensores en alerta -> frecuencia objetivo del variador (Hz)
FREQUENCY_BY_ALERTS = {0: 10.0, 1: 20.0, 2: 30.0, 3: 40.0}
FREQUENCY_RAMP_HZ_PER_TICK = 2.0  # rampa de aceleración/desaceleración del variador

# Cada sensor alterna entre "episodios" normales y de alerta para poder ver cómo reacciona el sistema.
ALERT_EPISODE_PROBABILITY = 0.4
EPISODE_TICKS = (8, 20)


def new_episode(variable):
    low, high, normal, _, threshold = VARIABLE_RANGES[variable]
    if random.random() < ALERT_EPISODE_PROBABILITY:
        target = random.uniform(threshold * 1.15, min(high, threshold * 1.8))
    else:
        target = normal
    return target, random.randint(*EPISODE_TICKS)


def build_state():
    state = {}
    for variable, (_, _, normal, _, _) in VARIABLE_RANGES.items():
        target, ticks = new_episode(variable)
        state[variable] = {"value": normal, "target": target, "ticks_left": ticks}
    return state


def step_value(variable, s):
    low, high, _, noise, _ = VARIABLE_RANGES[variable]
    if s["ticks_left"] <= 0:
        s["target"], s["ticks_left"] = new_episode(variable)
    s["ticks_left"] -= 1
    candidate = s["value"] + (s["target"] - s["value"]) * 0.15 + random.uniform(-noise, noise) * 0.5
    s["value"] = max(low, min(high, candidate))
    return s["value"]


def publish(client, slug, variable, value):
    payload = {
        "value": round(value, 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "token": DEVICE_TOKENS.get(slug, ""),
    }
    client.publish(f"{MQTT_TOPIC_PREFIX}/{slug}/{variable}", json.dumps(payload), qos=1)


def main():
    client = mqtt.Client()
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, keepalive=60)
    client.loop_start()

    state = build_state()
    frequency = FREQUENCY_BY_ALERTS[0]
    print(f"Simulator publishing to {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT} every {PUBLISH_INTERVAL_SECONDS}s")
    for slug in [*SENSOR_DEVICES, PLC_DEVICE]:
        if slug not in DEVICE_TOKENS:
            print(f"WARNING: no token configured for '{slug}' in SIMULATOR_DEVICE_TOKENS; "
                  f"its readings will be rejected by the listener until you add one.")

    try:
        while True:
            alerts = 0
            for slug, variable in SENSOR_DEVICES.items():
                value = step_value(variable, state[variable])
                publish(client, slug, variable, value)
                if value >= VARIABLE_RANGES[variable][4]:
                    alerts += 1

            target_hz = FREQUENCY_BY_ALERTS[alerts]
            if frequency < target_hz:
                frequency = min(target_hz, frequency + FREQUENCY_RAMP_HZ_PER_TICK)
            else:
                frequency = max(target_hz, frequency - FREQUENCY_RAMP_HZ_PER_TICK)

            publish(client, PLC_DEVICE, "sensores_en_alerta", alerts)
            publish(client, PLC_DEVICE, "frecuencia_hz", frequency)
            time.sleep(PUBLISH_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
