"""Simulated Galaxy Watch: sends synthetic data with the same protocol as watch-app,
so the server and dashboard can be tested without the real watch.

    python tools/fake_watch.py                       # ws://localhost:8765/watch
    python tools/fake_watch.py --url ws://192.168.0.XX:8765/watch
"""
import argparse
import asyncio
import json
import math
import random
import time

from websockets.asyncio.client import connect

SENSORS = ["ACCELERATION", "GRAVITY", "GYROSCOPE", "GYROSCOPE_ROTATION_VECTOR", "GYROSCOPE_UNCALIBRATED",
           "HRM_RAW", "LIGHT", "LINEAR_ACCELERATION", "PRESSURE"]
UNSUPPORTED = {"MAGNETIC": "NotSupportedError: sensor not supported",
               "STRESS_MONITOR": "NotSupportedError: STRESS_MONITOR not supported",
               "SLEEP_DETECTOR": "NotSupportedError: SLEEP_DETECTOR not supported"}
STREAMED = SENSORS + ["HRM", "PEDOMETER", "WRIST_UP", "ORIENTATION", "BATTERY", "BEZEL", "GPS", "SLEEP_MONITOR"]


def now_ms():
    return int(time.time() * 1000)


def motion(t):
    """Arm swinging while walking (~1.8 Hz) plus noise."""
    swing = math.sin(2 * math.pi * 1.8 * t)
    pitch = 0.6 * swing
    grav = (9.81 * math.sin(pitch), 0.8, 9.81 * math.cos(pitch))
    lin = (2.5 * swing + random.gauss(0, .15), 1.2 * math.sin(2 * math.pi * 3.6 * t) + random.gauss(0, .15),
           1.8 * math.cos(2 * math.pi * 1.8 * t) + random.gauss(0, .15))
    gyro = (60 * math.cos(2 * math.pi * 1.8 * t) + random.gauss(0, 2), random.gauss(0, 3), 15 * swing + random.gauss(0, 2))
    return grav, lin, gyro


def ppg(t, bpm):
    phase = (t * bpm / 60) % 1
    pulse = math.exp(-((phase - .2) ** 2) / .004) + .35 * math.exp(-((phase - .45) ** 2) / .01)
    return 2_000_000 - 40_000 * pulse + 3_000 * math.sin(2 * math.pi * .25 * t) + random.gauss(0, 400)


async def run(url, hz):
    async with connect(url, compression=None) as ws:
        print(f"conectado a {url}")
        await ws.send(json.dumps({"type": "hello", "app": "fake-1.0.0", "t": now_ms(), "available": SENSORS,
                                  "device": {"model_name": "SM-R800 (simulado)", "platform.version": "5.5.0",
                                             "platform.name": "Tizen"}}))
        for name in STREAMED:
            await ws.send(json.dumps({"type": "status", "source": name, "state": "waiting", "detail": "", "t": now_ms()}))
        for name, detail in UNSUPPORTED.items():
            await ws.send(json.dumps({"type": "status", "source": name, "state": "unsupported", "detail": detail, "t": now_ms()}))

        t_start = time.time()
        tick = 0
        steps = 0
        battery = 87
        period = 1 / hz
        next_send = time.perf_counter()
        while True:
            # Pace first, then stamp from the live clock: t_start + ideal time drifts away from the
            # wall clock over long runs (clock adjustments) and the latency readouts go negative.
            next_send += 0.05
            await asyncio.sleep(max(0, next_send - time.perf_counter()))
            samples = []
            per_batch = max(1, round(0.05 / period))
            base_ms = time.time() * 1000
            for j in range(per_batch):  # one 50 ms batch, like the watch
                tick += 1
                t = tick * period
                ts = int(base_ms - (per_batch - 1 - j) * period * 1000)
                bpm = 72 + 6 * math.sin(2 * math.pi * t / 40)
                grav, lin, gyro = motion(t)
                acc = tuple(g + l for g, l in zip(grav, lin))
                half = math.radians(gyro[2]) * .01
                samples += [
                    ["ACCELERATION", ts, dict(zip("xyz", acc))],
                    ["GRAVITY", ts, dict(zip("xyz", grav))],
                    ["LINEAR_ACCELERATION", ts, dict(zip("xyz", lin))],
                    ["GYROSCOPE", ts, dict(zip("xyz", gyro))],
                    ["GYROSCOPE_UNCALIBRATED", ts, {**dict(zip("xyz", gyro)), "xAxisDrift": .1, "yAxisDrift": -.05, "zAxisDrift": .02}],
                    ["GYROSCOPE_ROTATION_VECTOR", ts, {"x": .3 * math.sin(.4 * t), "y": .1, "z": math.sin(half + .2 * t) * .5, "w": .8}],
                    ["HRM_RAW", ts, {"lightType": "LED_GREEN", "lightIntensity": ppg(t, bpm)}],
                ]
                if tick % 2 == 0:
                    samples.append(["ORIENTATION", ts, {"alpha": (20 * t) % 360, "beta": 30 * math.sin(2 * math.pi * 1.8 * t),
                                                        "gamma": 10 * math.cos(t), "absolute": False}])
                if tick % 10 == 0:
                    samples.append(["PRESSURE", ts, {"pressure": 1013.2 + .05 * math.sin(t / 7) + random.gauss(0, .01)}])
                    samples.append(["LIGHT", ts, {"lightLevel": max(0, 320 + 80 * math.sin(t / 5) + random.gauss(0, 5))}])
                if tick % hz == 0:
                    samples.append(["HRM", ts, {"heartRate": round(bpm), "rRInterval": round(60000 / bpm)}])
                    steps += 2
                    samples.append(["PEDOMETER", ts, {"stepStatus": "WALKING", "speed": 4.8, "walkingFrequency": 1.8,
                                                      "cumulativeDistance": steps * .72, "cumulativeCalorie": steps * .04,
                                                      "cumulativeTotalStepCount": steps, "cumulativeWalkStepCount": steps,
                                                      "cumulativeRunStepCount": 0}])
                if tick % (hz * 5) == 0:
                    samples.append(["GPS", ts, {"latitude": 19.4326 + t * 1e-6, "longitude": -99.1332, "altitude": 2240,
                                                "accuracy": 8, "speed": 1.3, "heading": 90}])
                if tick % (hz * 30) == 0:
                    battery = max(1, battery - 1)
                    samples.append(["BATTERY", ts, {"level": battery / 100, "isCharging": False}])
                if tick == hz or tick % (hz * 60) == 0:
                    samples.append(["SLEEP_MONITOR", ts, {"status": "AWAKE", "timestamp": ts}])
                if random.random() < 0.3 / hz:
                    samples.append(["WRIST_UP", ts, {}])
                if random.random() < 1 / hz:
                    samples.append(["BEZEL", ts, {"direction": random.choice(["CW", "CCW"])}])
            await ws.send(json.dumps({"type": "data", "t": now_ms(), "samples": samples}))


def main():
    parser = argparse.ArgumentParser(description="Reloj simulado para GearStream")
    parser.add_argument("--url", default="ws://localhost:8765/watch")
    parser.add_argument("--hz", type=int, default=100, help="frecuencia de los sensores de movimiento")
    args = parser.parse_args()
    try:
        asyncio.run(run(args.url, args.hz))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
