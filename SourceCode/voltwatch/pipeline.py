"""Orchestrates the whole flow once at start-up:
   data -> baselines -> features -> model -> per-parameter analysis -> per-station briefing -> fleet view."""
import numpy as np
import pandas as pd
from .config import ASSETS, PARAMS, START
from .simulate import load_or_generate
from .features import learn_baselines, build_features, FEAT_LABEL
from .model import BreachModel, FleetAnomaly
from .forecast import forecast, FORECAST_H
from . import advisor


def _ms(ts):
    return [int(pd.Timestamp(t).timestamp() * 1000) for t in ts]


def _r(a, n):
    return [None if (v is None or (isinstance(v, float) and np.isnan(v))) else round(float(v), n) for v in a]


class Pipeline:
    def __init__(self):
        raw = load_or_generate().sort_values(["asset", "ts"]).reset_index(drop=True)
        self.raw, self.now = raw, raw.ts.max()
        self.frames = {a["id"]: raw[raw.asset == a["id"]].reset_index(drop=True) for a in ASSETS}
        self.mu, self.sd = learn_baselines(self.frames)
        self.F, Zs = build_features(self.frames, self.mu, self.sd)
        self.brain = BreachModel(self.F)
        self.anom = FleetAnomaly(Zs)
        self.results = {a["id"]: self._station(a) for a in ASSETS}

    # --- one parameter of one station -------------------------------------------------------
    def _param(self, aid, p):
        m, s, dec = PARAMS[p], PARAMS[p]["sign"], PARAMS[p]["dec"]
        d, F = self.frames[aid], self.F[(aid, p)]
        hr = d.ts.dt.hour.values
        x_now, exp_now = float(d[p].iloc[-3:].mean()), float(self.mu[(aid, p)][hr[-3:]].mean())
        z = float(F.z6.iloc[-1])
        abnormal = bool((F.z6.iloc[-12:] >= 3).sum() >= 8)             # >= 8 of last 12 h above 3 sigma
        onset = None
        if abnormal:
            below = np.where(F.z6.rolling(24, min_periods=12).median().values < 2)[0]
            onset = d.ts.iloc[min((below[-1] + 1) if len(below) else 0, len(d) - 1)]
        prob, attrib = self.brain.explain(F.iloc[-1:].fillna(0))
        fc = forecast(d[p].values, hr, self.mu[(aid, p)], m)
        risk = round(prob * 100, 1)
        breached = bool(s * (x_now - m["crit"]) > 0)
        status = advisor.classify(breached, risk, fc["eta"], abnormal)
        mu7, sd7 = self.mu[(aid, p)][hr[-168:]], self.sd[(aid, p)][hr[-168:]]
        daily = d.set_index("ts")[p].resample("D").max() if s > 0 else d.set_index("ts")[p].resample("D").min()
        drivers = sorted(attrib, key=lambda t: -t[1])
        tot = sum(max(v, 0) for _, v in drivers) or 1.0
        q = dict(key=p, label=m["label"], unit=m["unit"], group=m["group"], dec=dec, sign=s, crit=m["crit"], warn=round(m["warn"], 3),
                 status=status, breached=breached, current=round(x_now, dec + 1), expected=round(exp_now, dec + 1),
                 deviation=round(s * (x_now - exp_now), dec + 1), z=round(z, 1), abnormal=abnormal,
                 onset_label=onset.strftime("%d %b") if onset is not None else None, risk=risk,
                 eta=fc["eta"], eta_early=fc["eta_early"], eta_late=fc["eta_late"], trend_significant=fc["significant"],
                 drift_per_day=round(fc["drift_per_day"], dec + 2), margin_used=round(float(F.prox24.iloc[-1]) * 100, 0),
                 drivers=[dict(label=FEAT_LABEL[f], share=round(max(v, 0) / tot * 100, 0)) for f, v in drivers[:4] if v > 0.001],
                 live=dict(t=_ms(d.ts.iloc[-168:]), v=_r(d[p].iloc[-168:], dec + 1), mu=_r(mu7, dec + 1),
                           lo=_r(mu7 - 3 * sd7, dec + 1), hi=_r(mu7 + 3 * sd7, dec + 1)),
                 forecast=dict(t=_ms([self.now + pd.Timedelta(hours=i) for i in range(FORECAST_H)]),
                               mean=_r(fc["mean"], dec + 1), lo=_r(fc["lo"], dec + 1), hi=_r(fc["hi"], dec + 1)),
                 history=dict(t=_ms(daily.index), v=_r(daily.values, dec + 1)))
        q["insights"] = advisor.insights(q)
        return q

    # --- one station ------------------------------------------------------------------------
    def _station(self, a):
        aid = a["id"]
        P = {p: self._param(aid, p) for p in PARAMS}
        pl = list(P.values())
        worst = max(pl, key=lambda q: (advisor.RANK[q["status"]], q["risk"]))
        status = worst["status"]
        items, prec, hyp, causes = advisor.checklist(pl)
        risk = 1 - np.prod([1 - q["risk"] / 100 for q in pl])         # chance that at least one parameter breaches
        return dict(id=aid, name=a["name"], area=a["area"], pin=a["pin"], lat=a["lat"], lon=a["lon"], kind=a["kind"],
                    risk=round(float(risk) * 100, 0), status=status, top_param=worst["key"],
                    headline=advisor.headline(status, worst), due=advisor.due_by(status, pl),
                    anomaly_share=round(self.anom.share_last_24h(aid) * 100, 0),
                    n_abnormal=sum(q["abnormal"] for q in pl), n_watch=sum(q["status"] != "healthy" for q in pl),
                    params=P, checklist=items, precautions=prec, hypotheses=hyp, causes=causes,
                    signals=sorted([dict(key=q["key"], label=q["label"], risk=q["risk"], status=q["status"]) for q in pl],
                                   key=lambda t: -t["risk"])[:6])

    # --- fleet view (map, queue, heat-map) -----------------------------------------------------
    def fleet(self):
        rows = []
        for r in self.results.values():
            w = r["params"][r["top_param"]]
            rows.append(dict(id=r["id"], name=r["name"], area=r["area"], lat=r["lat"], lon=r["lon"], risk=r["risk"],
                             status=r["status"], top_label=w["label"], top_key=w["key"], eta=w["eta"], headline=r["headline"],
                             n_watch=r["n_watch"], n_abnormal=r["n_abnormal"],
                             heat={k: dict(risk=q["risk"], status=q["status"], z=q["z"]) for k, q in r["params"].items()}))
        rows.sort(key=lambda r: (-advisor.RANK[r["status"]], -r["risk"]))
        return dict(assets=rows, now=int(self.now.timestamp() * 1000), metrics=self.brain.metrics, rows=int(len(self.raw)),
                    days=int((self.now - START).days) + 1,
                    params={k: dict(label=v["label"], group=v["group"]) for k, v in PARAMS.items()})
