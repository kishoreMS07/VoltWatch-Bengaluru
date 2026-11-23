"""STEP 5-6 - turn numbers into decisions: status, plain-language insights, precautions and the field checklist."""
from .config import PLAYBOOK, COMBOS

RANK = {"healthy": 0, "watch": 1, "high": 2, "critical": 3}


def fmt(v, d):
    return f"{v:,.{d}f}"


def classify(breached, risk, eta, abnormal):
    if breached:
        return "critical"
    if risk >= 60 or (eta is not None and eta <= 48):
        return "high"
    if risk >= 15 or (eta is not None and eta <= 168) or abnormal:
        return "watch"
    return "healthy"


def insights(q):
    """Three short sentences: what is off, how close to the limit, when it will cross."""
    d, u = q["dec"], q["unit"]
    if q["status"] == "healthy":
        return [f"{q['label']} is following its normal pattern for this station."]
    out = []
    if q["abnormal"]:
        out.append(f"{q['label']} is running {fmt(abs(q['deviation']), d)} {u} {'worse' if q['deviation'] > 0 else 'better'} than this "
                   f"station's own baseline for this hour (z = {q['z']}), abnormal since {q['onset_label']}.")
    else:
        out.append(f"{q['label']} is {fmt(abs(q['deviation']), d)} {u} from its own baseline (z = {q['z']}), still inside the normal band but moving.")
    out.append(f"Now {fmt(q['current'], d)} {u} against a critical limit of {fmt(q['crit'], d)} {u}; "
               f"{int(q['margin_used'])} % of the healthy safety margin is used.")
    if q["breached"]:
        out.append("The critical limit has already been crossed.")
    elif q["eta"] is not None and q["trend_significant"]:
        rng = f" (likely {q['eta_early']} to {q['eta_late']} h)" if q["eta_early"] and q["eta_late"] else ""
        out.append(f"At the current drift of {fmt(abs(q['drift_per_day']), d + 1)} {u} per day, the limit will be crossed in about {q['eta']} h{rng}.")
    else:
        out.append("No statistically significant trend yet, so no crossing is projected in the next 10 days.")
    return out


def checklist(plist):
    ranked = sorted([q for q in plist if q["status"] != "healthy"], key=lambda q: (-RANK[q["status"]], -q["risk"]))
    items, precautions = [], []
    for q in ranked[:3]:
        pb, urgent = PLAYBOOK[q["key"]], q["status"] in ("critical", "high")
        if urgent:
            precautions += [t for t in pb["precautions"] if t not in precautions]
        for j, a in enumerate(pb["actions"][: 4 if urgent else 2]):
            prio = "P1" if (urgent and j < 2) else ("P2" if urgent or j == 0 else "P3")
            items.append(dict(text=a, prio=prio, param=q["label"], key=f"{q['key']}-{j}"))
    items.sort(key=lambda t: t["prio"])
    keys = {q["key"] for q in ranked}
    hyp = [dict(text=t, confidence=int(min(95, 40 + 25 * len(c & keys)))) for c, t in COMBOS if len(c & keys) >= 2]
    hyp.sort(key=lambda h: -h["confidence"])
    causes = [dict(param=q["label"], cause=PLAYBOOK[q["key"]]["causes"][0]) for q in ranked[:2]]
    return items[:9], precautions, hyp[:2], causes


def due_by(status, plist):
    if status == "critical":
        return "Immediately"
    etas = [q["eta_early"] or q["eta"] for q in plist if q["status"] == "high" and (q["eta_early"] or q["eta"])]
    if etas:
        return f"Within {int(max(min(etas) - 12, 4))} h"      # leave a 12 h safety buffer before the earliest ETA
    return "Next scheduled visit (within 7 days)" if status == "watch" else None


def headline(status, worst):
    u, d = worst["unit"], worst["dec"]
    if status == "critical":
        return f"{worst['label']} has crossed its critical limit of {fmt(worst['crit'], d)} {u}."
    if status == "high":
        tail = f" in about {worst['eta']} h." if worst["eta"] else "."
        return f"{worst['label']} is expected to cross {fmt(worst['crit'], d)} {u}{tail}"
    if status == "watch":
        return f"{worst['label']} is drifting from its baseline. No crossing expected in the next 48 h."
    return "All 12 parameters are following their normal pattern."
