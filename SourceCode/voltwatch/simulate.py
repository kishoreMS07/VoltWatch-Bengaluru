"""STEP 0 - make the sample data: 8 Bengaluru stations x 12 parameters x 3,600 hours (5 months).

Each reading = typical value + load effect (evening and morning charging peaks, quieter weekends)
             + ambient-temperature effect + sensor noise + (optional) a fault episode ramping toward the limit.
Fault episodes live in config.EPISODES. The model never sees them; it only sees the readings.
"""
from pathlib import Path
import numpy as np
import pandas as pd
from .config import ASSETS, PARAMS, EPISODES, START, DAYS, AMBIENT_REF

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "telemetry.csv"


def load_profile(hour):
    """0..1 charging demand through the day: morning commute bump + big evening peak."""
    h = np.asarray(hour, dtype=float)
    return np.clip(0.12 + 0.75 * np.exp(-((h - 18.5) / 2.6) ** 2) + 0.5 * np.exp(-((h - 9.0) / 2.2) ** 2), 0, 1)


def generate(seed=42):
    rng = np.random.default_rng(seed)
    idx = pd.date_range(START, periods=DAYS * 24, freq="h")
    n = len(idx)
    hour, dow, day = idx.hour.values, idx.dayofweek.values, np.arange(n) / 24.0
    # Bengaluru: ~27 C in June easing to ~23 C by November, +-4 C through the day
    ambient = 25 - 2.0 * day / DAYS + 4 * np.sin(2 * np.pi * (hour - 8) / 24) + rng.normal(0, 0.8, n)
    frames = []
    for a in ASSETS:
        dayf = np.repeat(rng.normal(1.0, 0.07, DAYS + 1), 24)[:n]            # day-to-day demand variation
        load = load_profile(hour) * np.where(dow >= 5, 0.8, 1.0) * dayf * a["scale"]
        df = pd.DataFrame({"ts": idx, "asset": a["id"], "ambient": ambient.round(2)})
        for k, m in PARAMS.items():
            x = m["base"] + m["load"] * load + m["amb"] * (ambient - AMBIENT_REF) + rng.normal(0, m["noise"], n)
            for e in EPISODES:                                                # inject this asset's fault story
                if e["a"] == a["id"] and e["p"] == k:
                    ramp = np.clip((day - e["start"]) / (e["peak"] - e["start"]), 0, 1) ** e["pw"]
                    if e["repair"] is not None:
                        ramp = np.where(day >= e["repair"], 0.0, ramp)         # field repair resets the drift
                    x = x + m["sign"] * e["f"] * m["margin"] * ramp
            for _ in range(6):                                                # isolated sensor glitches
                x[rng.integers(30, n)] += rng.choice([-1, 1]) * 6 * m["noise"]
            df[k] = x
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    for k, m in PARAMS.items():
        out[k] = out[k].round(m["dec"] + 1)
    return out


def load_or_generate():
    if DATA_FILE.exists():
        return pd.read_csv(DATA_FILE, parse_dates=["ts"])
    DATA_FILE.parent.mkdir(exist_ok=True)
    df = generate()
    df.to_csv(DATA_FILE, index=False)
    return df


if __name__ == "__main__":
    DATA_FILE.parent.mkdir(exist_ok=True)
    d = generate()
    d.to_csv(DATA_FILE, index=False)
    print(f"Wrote {len(d):,} rows to {DATA_FILE}")
