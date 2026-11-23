# VoltWatch Bengaluru - Asset Intelligence (Python / Flask)

Predictive maintenance for 8 EV charging stations across Bengaluru. For every station and each of 12 parameters it tells you
what is happening, what is abnormal, what will happen and when, why the AI thinks so, and what the field team should do.

## Run
```bash
pip install -r requirements.txt
python -m voltwatch.simulate     # optional: regenerate data/telemetry.csv
python app.py                    # http://127.0.0.1:5000   (about 6 s to start: it trains the model)
```
The browser needs internet for Chart.js and the fonts.

## Project layout
```
app.py                  Flask: /  /api/fleet  /api/station/<id>
voltwatch/config.py     stations (lat/lon), 12 parameters + limits, fault stories, field playbook
voltwatch/simulate.py   STEP 0  synthetic 5-month hourly data
voltwatch/features.py   STEP 1-2  own-baseline learning + feature engineering + labels
voltwatch/model.py      STEP 3  breach-risk model, evaluation, explanation, multi-signal anomaly
voltwatch/forecast.py   STEP 4  trend forecast, ETA, risk window
voltwatch/advisor.py    STEP 5  status, insights, precautions, checklist, act-by time
voltwatch/pipeline.py   runs everything once and builds the JSON the UI reads
templates/index.html, static/style.css, static/app.js   five-step dashboard
```

## How it works (end to end)

**0. Data.** `simulate.py` creates 150 days x 24 h x 8 stations x 12 parameters = 28,800 rows. Each value =
typical level + charging-load effect (morning and evening peaks, quieter weekends) + ambient temperature effect + noise.
`config.EPISODES` then adds fault stories: five breaches that happened and were repaired (for example Koramangala's leakage current
rose through August, the monsoon, until an insulation repair), and six faults still developing today
(Indiranagar connector overheating, Whitefield fan wearing out, Electronic City battery ageing, and others).
The model never sees those definitions, only the readings.

**1. Own baseline.** For each station, parameter and hour of day, the first 21 days give a mean and spread. This is the asset's "healthy
self". Judging a station against itself avoids false alarms from stations that simply run hotter or busier.

**2. Features.** Every hour, each parameter is described by 8 numbers, all oriented so "bigger = worse":
closeness to limit, drift from baseline, z-score, 24 h rate of change, 3-day trend, volatility, stress on the other parameters,
and time-to-limit at the current rate.

**3. Risk model.** A gradient-boosting classifier learns P(limit crossed within the next 48 h). Monotonic constraints keep it sensible
(more drift can never reduce risk). Class weighting handles how rare breaches are. It is trained on days 1-105 and tested on days 106-150.
A second model, IsolationForest, looks at all 12 z-scores together and flags unusual combinations.

**4. Forecast and window.** The drift of the last 4 days is fitted with a line plus its uncertainty. If the slope is clearly real
(over 2 standard errors) it is projected on top of the daily pattern. The first hour that crosses the limit is the ETA, and the
slope's 80 % range gives the risk window.

**5. Explain.** For each parameter the model's inputs are replaced one at a time with healthy values; the drop in risk shows how much that
input contributed (occlusion). The UI shows these as "what drove the score" plus a ranking of all parameters.

**6. Act.** `advisor.py` sets the status (healthy / watch / high / critical), writes the plain-language insight, and picks precautions
and a checklist (P1 first) from the playbook. When several parameters of one pattern move together it names a root cause, for example
connector plus cable temperature = rising contact resistance. "Act by" = earliest ETA minus a 12 h safety buffer.

## Use your own data
Replace `data/telemetry.csv` with columns `ts, asset, ambient` + the 12 parameter columns (hourly). Edit stations, limits and the
playbook in `voltwatch/config.py`. Remove `EPISODES` if you do not want synthetic faults.

## Honest limits
Data is synthetic; metrics come from only 2 unseen breaches. Slow ageing is judged against the first-3-weeks baseline; in production
refresh baselines periodically and validate on real incident logs.
