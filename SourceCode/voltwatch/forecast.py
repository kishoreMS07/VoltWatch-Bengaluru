"""STEP 4 - 'what is likely to happen?': trend forecast, time-to-limit (ETA) and the risk window.

1. residual = reading - own baseline for that hour (removes the daily charging cycle)
2. fit a straight line through the last 96 h of 6-hour residual averages -> slope and its uncertainty
3. only trust the slope if it is > 2 standard errors in the bad direction (otherwise 'no real trend')
4. forecast = baseline profile for each future hour + extrapolated drift
5. ETA = first future hour that crosses the limit; risk window = ETA using slope +-1.28 sigma (80 % band)
"""
import numpy as np

FORECAST_H = 240


def forecast(x, hours, mu_arr, meta):
    s = meta["sign"]
    r = x - mu_arr[hours]
    blocks = r[-96:].reshape(16, 6).mean(axis=1)
    tb = np.arange(16) * 6 + 2.5
    (slope, icpt), cov = np.polyfit(tb, blocks, 1, cov=True)
    sig = float(np.sqrt(max(cov[0, 0], 1e-12)))
    level = slope * 95 + icpt
    k = np.arange(1, FORECAST_H + 1)
    base_f = mu_arr[(hours[-1] + k) % 24]
    sb = s * slope                                         # slope in the 'bad' direction (per hour)
    significant = bool(sb > 2 * sig)
    mean_p = base_f + level + (slope if significant else 0.0) * k
    early = base_f + level + s * (max(sb, 0) + 1.28 * sig) * k
    late = base_f + level + s * max(sb - 1.28 * sig, 0) * k

    def eta(path):
        hit = s * (path - meta["crit"]) > 0
        return int(np.argmax(hit)) + 1 if hit.any() else None

    return dict(mean=mean_p, lo=np.minimum(early, late), hi=np.maximum(early, late), significant=significant,
                eta=eta(mean_p), eta_early=eta(early), eta_late=eta(late), drift_per_day=float(slope * 24))
