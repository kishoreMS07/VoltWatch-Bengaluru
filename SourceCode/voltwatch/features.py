"""STEP 1-2 - learn each asset's own healthy baseline, then turn raw readings into model features.

Baseline: for every (station, parameter, hour-of-day) we learn mean and spread from the first 21 days.
Because it is learned per station AND per hour, a 62 C connector at 6 pm can be normal on one station
and alarming on another.

Features (all measured in the 'bad' direction, so high = worse for every parameter):
  prox24    closeness to the limit: worst reading of the last 24 h as a share of the healthy safety margin
  dev6      6 h average drift from baseline, as a share of the margin
  z6        the same drift in standard deviations (statistical abnormality)
  slope24   change of dev6 over 24 h        slope72  average daily change of dev6 over 3 days
  vol24     24 h volatility                 cross    worst abnormality among the OTHER parameters of the station
  eta_feat  log(hours to limit if the 24 h rate continues, capped at 240)
Label y = the limit is crossed at any point in the next 48 h.
"""
import numpy as np
import pandas as pd
from .config import PARAMS, BASE_DAYS

HORIZON = 48
FEATS = ["prox24", "dev6", "z6", "slope24", "slope72", "vol24", "cross", "eta_feat"]
FEAT_LABEL = {
    "prox24": "Closeness to the limit", "dev6": "Drift from own baseline", "z6": "Statistical abnormality",
    "slope24": "Rate of change (24 h)", "slope72": "Trend over 3 days", "vol24": "Volatility",
    "cross": "Stress on other parameters", "eta_feat": "Time-to-limit at current rate",
}


def learn_baselines(frames):
    mu, sd = {}, {}
    for aid, d in frames.items():
        base = d.iloc[: BASE_DAYS * 24]
        by_hour = base.groupby(base.ts.dt.hour)
        for p in PARAMS:
            m, s = by_hour[p].mean().values, by_hour[p].std().values
            mu[(aid, p)] = m
            sd[(aid, p)] = np.maximum(s, 0.7 * np.median(s))     # floor so quiet hours do not explode z-scores
    return mu, sd


def build_features(frames, mu, sd):
    F = {}
    for aid, d in frames.items():
        hr = d.ts.dt.hour.values
        parts, Z = {}, {}
        for p, m in PARAMS.items():
            s, M = m["sign"], m["margin"]
            x = d[p]
            r = x - pd.Series(mu[(aid, p)][hr], index=d.index)             # residual vs own baseline
            sdv = pd.Series(sd[(aid, p)][hr], index=d.index)
            r6 = r.rolling(6, min_periods=3).mean()
            z6 = s * r6 * np.sqrt(6) / sdv
            dev6 = s * r6 / M
            prox24 = (s * (x - m["worst"]) / M).rolling(24, min_periods=12).max()
            slope24 = dev6 - dev6.shift(24)
            slope72 = (dev6 - dev6.shift(72)) / 3
            vol24 = r.rolling(24).std() / M
            rate = slope24.clip(lower=0)
            hrs = np.where(rate > 0.002, (1 - prox24).clip(lower=0) / rate * 24, 240.0)
            bad = (s * (x - m["crit"]) > 0).astype(float)                    # 1 when beyond the critical limit
            y = bad.shift(-1)[::-1].rolling(HORIZON, min_periods=HORIZON).max()[::-1]   # breach in next 48 h?
            parts[p] = pd.DataFrame(dict(prox24=prox24, dev6=dev6, z6=z6, slope24=slope24, slope72=slope72,
                                         vol24=vol24, eta_feat=np.log1p(np.minimum(hrs, 240.0)), y=y,
                                         now_bad=bad.rolling(6, min_periods=1).max(), ts=d.ts))
            Z[p] = z6
        Zm = pd.DataFrame(Z)
        for p in PARAMS:
            parts[p]["cross"] = Zm.drop(columns=p).max(axis=1).clip(lower=0)
            F[(aid, p)] = parts[p]
    return F, {aid: pd.DataFrame({p: F[(aid, p)].z6 for p in PARAMS}).fillna(0) for aid in frames}
