"""STEP 3 - the breach-risk model and its explanation.

HistGradientBoostingClassifier learns  P(limit crossed within 48 h | features).
 * monotonic constraints: more drift / closer to limit can never LOWER the risk (keeps it sane and explainable)
 * class_weight='balanced': breaches are rare, so without it the model would just say 'no breach' every time
 * honest evaluation: train on days 1-105, test on days 106-150 that the model never saw
Explanation = occlusion: replace one feature by its healthy median and see how much the probability drops.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, IsolationForest
from sklearn.metrics import roc_auc_score, average_precision_score, precision_score, recall_score
from .config import START, PARAMS, BASE_DAYS
from .features import FEATS, HORIZON

MONOTONIC = [1, 1, 1, 1, 1, 0, 0, -1]


def _new():
    return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.06, max_iter=200, l2_regularization=1.0,
                                          monotonic_cst=MONOTONIC, class_weight="balanced", random_state=0)


class BreachModel:
    def __init__(self, F):
        rows = []
        for (aid, p), f in F.items():
            g = f.iloc[96::3].copy()                  # every 3rd hour, skip rolling-window warm-up
            g["asset"], g["param"] = aid, p
            rows.append(g)
        D = pd.concat(rows)
        D = D[D.now_bad == 0].dropna(subset=FEATS + ["y"])   # only ask 'will it breach?' while still inside limits
        cut = START + pd.Timedelta(days=105)
        tr, te = D[D.ts < cut], D[D.ts >= cut]
        m = _new().fit(tr[FEATS], tr.y)
        pt = m.predict_proba(te[FEATS])[:, 1]
        leads = []                                     # how early did we pass 50 % before each unseen breach?
        for (aid, p), g in te.assign(pr=pt).groupby(["asset", "param"]):
            pos = g[g.y == 1]
            if pos.empty:
                continue
            t0 = pos.ts.min() + pd.Timedelta(hours=1)
            w = g[(g.ts <= t0) & (g.ts >= t0 - pd.Timedelta(days=6)) & (g.pr >= 0.5)]
            if not w.empty:
                leads.append((t0 - w.ts.min()).total_seconds() / 3600)
        self.metrics = dict(
            auc=round(float(roc_auc_score(te.y, pt)), 3), avg_precision=round(float(average_precision_score(te.y, pt)), 3),
            precision=round(float(precision_score(te.y, pt >= .5, zero_division=0)), 3),
            recall=round(float(recall_score(te.y, pt >= .5, zero_division=0)), 3),
            median_lead_h=float(np.median(leads)) if leads else None, incidents_test=len(leads), horizon_h=HORIZON,
            train_rows=int(len(tr)), test_rows=int(len(te)), train_window="Days 1-105", test_window="Days 106-150 (unseen)")
        self.model = _new().fit(D[FEATS], D.y)         # deployed model learns from all history
        self.healthy = D[D.y == 0][FEATS].median()

    def prob(self, row):
        return float(self.model.predict_proba(row[FEATS])[:, 1][0])

    def explain(self, row):
        p0, out = self.prob(row), []
        for f in FEATS:
            alt = row[FEATS].copy()
            alt[f] = self.healthy[f]
            out.append((f, p0 - self.prob(alt)))
        return p0, out


class FleetAnomaly:
    """IsolationForest on all 12 z-scores at once: catches unusual COMBINATIONS even if no single limit is near."""
    def __init__(self, Zs):
        base = pd.concat([z.iloc[96: BASE_DAYS * 24] for z in Zs.values()])
        self.iso = IsolationForest(n_estimators=150, contamination=0.01, random_state=0).fit(base)
        self.Zs = Zs

    def share_last_24h(self, aid):
        return float((self.iso.predict(self.Zs[aid].iloc[-24:]) == -1).mean())
