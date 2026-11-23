"""Configuration: Bengaluru stations, the 12 monitored parameters, limits, injected fault stories, field playbook."""
import pandas as pd

END = pd.Timestamp("2026-11-16 00:00")      # end of the sample window (exclusive)
DAYS = 150                                   # 5 months of hourly telemetry (19 Jun - 15 Nov 2026)
START = END - pd.Timedelta(days=DAYS)
BASE_DAYS = 21                               # first 3 weeks = healthy baseline learning window
AMBIENT_REF = 27.0                           # reference ambient (deg C) for thermal coupling

ASSETS = [
    dict(id="BLR-01", name="Indiranagar 100 Ft Road", area="Indiranagar",     pin="560038", lat=12.9784, lon=77.6408, kind="60 kW DC fast charger",  scale=1.05),
    dict(id="BLR-02", name="Whitefield ITPL",         area="Whitefield",      pin="560066", lat=12.9855, lon=77.7285, kind="120 kW DC fast charger", scale=1.10),
    dict(id="BLR-03", name="Koramangala 5th Block",   area="Koramangala",     pin="560095", lat=12.9352, lon=77.6245, kind="60 kW DC fast charger",  scale=0.95),
    dict(id="BLR-04", name="Electronic City Phase 1", area="Electronic City", pin="560100", lat=12.8452, lon=77.6602, kind="Battery storage + charger", scale=1.00),
    dict(id="BLR-05", name="HSR Layout Sector 2",     area="HSR Layout",      pin="560102", lat=12.9116, lon=77.6474, kind="60 kW DC fast charger",  scale=0.92),
    dict(id="BLR-06", name="Jayanagar 4th Block",     area="Jayanagar",       pin="560011", lat=12.9250, lon=77.5938, kind="120 kW DC fast charger", scale=1.08),
    dict(id="BLR-07", name="Hebbal Flyover",          area="Hebbal",          pin="560024", lat=13.0358, lon=77.5970, kind="30 kW DC charger",       scale=0.90),
    dict(id="BLR-08", name="Bellandur Outer Ring Rd", area="Bellandur",       pin="560103", lat=12.9304, lon=77.6784, kind="60 kW DC fast charger",  scale=1.00),
]

# base: typical value at zero load | load: extra at peak load | crit: critical limit
PARAMS = {
    "cell_temp":             dict(label="Cell temperature",        unit="°C",   group="Thermal",    base=38.0, load=8.0,  noise=0.9,  crit=55.0, amb=0.25, dec=1),
    "cable_temp":            dict(label="Cable temperature",       unit="°C",   group="Thermal",    base=42.0, load=10.0, noise=1.2,  crit=70.0, amb=0.35, dec=1),
    "connector_temp":        dict(label="Connector temperature",   unit="°C",   group="Thermal",    base=45.0, load=10.0, noise=1.2,  crit=75.0, amb=0.35, dec=1),
    "fan_rpm":               dict(label="Cooling fan speed",       unit="rpm",  group="Cooling",    base=2600, load=300,  noise=45,   crit=1800, amb=0.0,  dec=0),
    "coolant_flow":          dict(label="Coolant flow",            unit="L/min",group="Cooling",    base=6.0,  load=0.3,  noise=0.08, crit=4.0,  amb=0.0,  dec=2),
    "voltage_drift":         dict(label="Voltage drift",           unit="mV",   group="Electrical", base=60.0, load=15.0, noise=4.0,  crit=120.0,amb=0.0,  dec=0),
    "internal_resistance":   dict(label="Internal resistance",     unit="mΩ",   group="Battery",    base=11.0, load=0.8,  noise=0.25, crit=18.0, amb=0.0,  dec=2),
    "leakage_current":       dict(label="Leakage current",         unit="mA",   group="Safety",     base=12.0, load=3.0,  noise=0.9,  crit=30.0, amb=0.0,  dec=1),
    "insulation_resistance": dict(label="Insulation resistance",   unit="MΩ",   group="Safety",     base=6.0,  load=0.0,  noise=0.15, crit=2.0,  amb=0.0,  dec=2),
    "ripple_voltage":        dict(label="DC ripple voltage",       unit="V",    group="Electrical", base=3.5,  load=0.8,  noise=0.2,  crit=8.0,  amb=0.0,  dec=2),
    "output_efficiency":     dict(label="Conversion efficiency",   unit="%",    group="Electrical", base=96.5, load=-1.0, noise=0.25, crit=92.0, amb=0.0,  dec=2),
    "battery_soh":           dict(label="Battery health (SoH)",    unit="%",    group="Battery",    base=96.0, load=0.0,  noise=0.12, crit=85.0, amb=0.0,  dec=2),
}
for _k, _m in PARAMS.items():
    _m["key"] = _k
    _m["sign"] = 1 if _m["crit"] > _m["base"] else -1            # +1 = high is bad, -1 = low is bad
    _m["worst"] = _m["base"] + (_m["load"] if _m["load"] * _m["sign"] > 0 else 0.0)
    _m["margin"] = abs(_m["crit"] - _m["worst"])                 # healthy worst-case -> critical
    _m["warn"] = _m["crit"] - _m["sign"] * 0.30 * _m["margin"]   # 70 % of margin consumed

# Fault episodes injected into the synthetic data (ground truth used ONLY to build the sample data).
# f = fraction of the safety margin consumed at the peak (>1 means the limit was breached).
# repair=None -> still developing at the end of the data window.
EPISODES = [
    # history: breach, then field repair
    dict(a="BLR-05", p="coolant_flow",          start=28,  peak=40,  repair=42,   f=1.35, pw=2.0),
    dict(a="BLR-05", p="cell_temp",             start=28,  peak=40,  repair=42,   f=0.55, pw=2.0),
    dict(a="BLR-03", p="leakage_current",       start=50,  peak=66,  repair=70,   f=1.30, pw=2.0),
    dict(a="BLR-03", p="insulation_resistance", start=50,  peak=66,  repair=70,   f=1.20, pw=2.0),
    dict(a="BLR-06", p="voltage_drift",         start=62,  peak=82,  repair=85,   f=1.35, pw=2.0),
    dict(a="BLR-07", p="connector_temp",        start=88,  peak=108, repair=111,  f=1.30, pw=2.0),
    dict(a="BLR-07", p="cable_temp",            start=88,  peak=108, repair=111,  f=0.50, pw=2.0),
    dict(a="BLR-08", p="cable_temp",            start=104, peak=124, repair=127,  f=1.30, pw=2.0),
    # live: developing right now
    dict(a="BLR-01", p="connector_temp",        start=122, peak=150, repair=None, f=0.96, pw=2.0),
    dict(a="BLR-01", p="cable_temp",            start=122, peak=150, repair=None, f=0.55, pw=2.0),
    dict(a="BLR-02", p="fan_rpm",               start=112, peak=150, repair=None, f=0.88, pw=1.6),
    dict(a="BLR-02", p="cell_temp",             start=112, peak=150, repair=None, f=0.50, pw=1.6),
    dict(a="BLR-04", p="internal_resistance",   start=95,  peak=150, repair=None, f=0.72, pw=1.5),
    dict(a="BLR-04", p="cell_temp",             start=95,  peak=150, repair=None, f=0.50, pw=1.5),
    dict(a="BLR-04", p="voltage_drift",         start=95,  peak=150, repair=None, f=0.65, pw=1.5),
    dict(a="BLR-04", p="battery_soh",           start=90,  peak=150, repair=None, f=0.45, pw=1.0),
    dict(a="BLR-06", p="ripple_voltage",        start=100, peak=150, repair=None, f=0.80, pw=1.8),
    dict(a="BLR-06", p="output_efficiency",     start=100, peak=150, repair=None, f=0.60, pw=1.8),
    dict(a="BLR-05", p="coolant_flow",          start=135, peak=150, repair=None, f=0.40, pw=1.5),
]

# ------------------------------------------------------------------ field playbook
PLAYBOOK = {
    "cell_temp": dict(
        causes=["Cooling path degraded (fan or coolant)", "Sustained high-power sessions in hot ambient", "Cell imbalance or ageing"],
        precautions=["Cap charging power to about 70 % on this station", "Avoid back-to-back fast sessions"],
        actions=["Inspect fan operation and clear the airflow path", "Check coolant level, filter and pump flow",
                 "Run a cell-balance and BMS temperature-sensor check", "Compare module temperatures to find a single hot module"]),
    "cable_temp": dict(
        causes=["Rising contact resistance in the cable assembly", "Damaged conductor strands or insulation", "Cable cooling fault"],
        precautions=["Limit session current to 80 %", "Tag the cable for visual check at the next session end"],
        actions=["Inspect charger cable and gland for kinks, burns or discolouration", "Thermal-scan the cable along its length under load",
                 "Re-torque cable lugs inside the cabinet", "Replace the cable if the hot-spot persists after re-torque"]),
    "connector_temp": dict(
        causes=["Worn or contaminated connector pins", "Loose crimp or terminal", "Poor mating with vehicle inlet"],
        precautions=["Derate power on this connector to 60 %", "Prefer the second gun if the station has one"],
        actions=["Inspect charger cable and connector pins for pitting, soot or debris", "Clean pins and check spring contact force",
                 "Re-torque and thermal-scan the terminal under load", "Replace the connector head if resistance is out of spec"]),
    "fan_rpm": dict(
        causes=["Bearing wear or blocked fan", "Dust-clogged filter", "Fan controller or PWM fault"],
        precautions=["Cap power to 70 % until the fan is serviced", "Do not run in an enclosed cabinet without airflow"],
        actions=["Check dock cooling fan for noise, wobble and obstruction", "Clean or replace the air filter",
                 "Measure fan current and PWM signal", "Swap the fan module if the speed cannot be restored"]),
    "coolant_flow": dict(
        causes=["Clogged coolant filter", "Pump wear or air lock", "Low coolant level or leak"],
        precautions=["Cap power to 70 %", "Do not clear alarms before flow is restored"],
        actions=["Check coolant level and top up with approved fluid", "Inspect and flush the coolant filter",
                 "Bleed air from the loop and test pump pressure", "Look for leaks at hose joints and the manifold"]),
    "voltage_drift": dict(
        causes=["Ageing or loose power connections", "Failing sense wiring", "Cell imbalance in the pack"],
        precautions=["Reduce output current by 20 %", "Pause fast sessions if drift grows during a session"],
        actions=["Inspect DC busbar and power terminals for heat marks", "Re-torque power connections and check sense wiring",
                 "Run a pack balancing cycle", "Log a voltage profile through one full session"]),
    "internal_resistance": dict(
        causes=["Normal cell ageing accelerated by heat", "Poor inter-cell connection", "Electrolyte degradation"],
        precautions=["Limit charge C-rate", "Keep SoC window between 20 % and 90 %"],
        actions=["Run a full battery health scan and compare against the last scan", "Check inter-cell busbar torque and corrosion",
                 "Review cell-level resistance to locate weak modules", "Plan module replacement if the trend continues"]),
    "leakage_current": dict(
        causes=["Moisture ingress", "Insulation damage", "Contaminated connector or cabinet seal"],
        precautions=["Stop charging immediately if the earth-fault alarm trips", "Keep the cabinet door closed"],
        actions=["Inspect cabinet seals and cable glands for water ingress", "Dry and clean the connector and inlet area",
                 "Run an insulation test at the cabinet and at the cable", "Replace damaged seals or cable sections"]),
    "insulation_resistance": dict(
        causes=["Moisture or condensation", "Insulation ageing", "Conductive dust deposits"],
        precautions=["Do not energise if insulation falls below the limit", "Avoid charging during heavy rain until checked"],
        actions=["Run an insulation resistance (megger) test per segment", "Inspect seals and drain points",
                 "Dry the cabinet and fit desiccant if needed", "Replace the failing cable or module"]),
    "ripple_voltage": dict(
        causes=["DC-link capacitor wear", "Power-module switching fault", "Loose DC connection"],
        precautions=["Reduce output power by 25 %", "Watch for efficiency loss and extra heat"],
        actions=["Inspect DC-link capacitors for bulging or leakage", "Measure ripple with a scope at the module output",
                 "Check power-module gate drive and cooling", "Replace the capacitor bank or module"]),
    "output_efficiency": dict(
        causes=["Power-module wear", "Fouled heatsink", "Failing capacitors"],
        precautions=["Reduce power and watch heat", "Review energy loss on the next billing run"],
        actions=["Clean heatsink and check thermal paste condition", "Compare input and output power under a fixed load",
                 "Inspect power-module temperatures", "Schedule module service"]),
    "battery_soh": dict(
        causes=["Calendar and cycle ageing", "Frequent deep discharge or fast-charge stress"],
        precautions=["Narrow the SoC window", "Avoid long idle at full charge"],
        actions=["Run a capacity test and update the health record", "Review cycle and temperature history",
                 "Plan module replacement or second-life reassignment"]),
}

# parameters that fail together point to one root cause
COMBOS = [
    ({"connector_temp", "cable_temp"}, "Rising contact resistance in the connector and cable path"),
    ({"leakage_current", "insulation_resistance"}, "Moisture ingress or insulation degradation"),
    ({"internal_resistance", "cell_temp", "voltage_drift", "battery_soh"}, "Battery cell ageing or imbalance"),
    ({"fan_rpm", "coolant_flow", "cell_temp"}, "Cooling path degradation"),
    ({"ripple_voltage", "output_efficiency", "voltage_drift"}, "Power-module or DC-link capacitor wear"),
]
