"""Central configuration: paths, dataset-to-elevator mappings and alert parameters."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
LOOKUP_CSV = ROOT / "data" / "fault_fix_lookup.csv"

SEED = 42
N_ELEVATORS = 100
TRAIN_END = "2015-09-01"  # model trains before this date, is evaluated (and shown) after it

ALERT_LEVELS = ["NORMAL", "PRELIMINARY", "WARNING", "LEVEL_3", "EMERGENCY"]
LEVEL_RANK = {lvl: i for i, lvl in enumerate(ALERT_LEVELS)}
LEVEL_COLORS = {
    "NORMAL": "#2ecc71",
    "PRELIMINARY": "#f1c40f",
    "WARNING": "#e67e22",
    "LEVEL_3": "#e74c3c",
    "EMERGENCY": "#8e0000",
}

# Sensor threshold levels are percentiles of the historical (training-period) distribution.
PERCENTILE_LEVELS = {"PRELIMINARY": 0.95, "WARNING": 0.99, "LEVEL_3": 0.999}
# Predicted failure probability -> alert level.
PROB_LEVELS = {"PRELIMINARY": 0.15, "WARNING": 0.35, "LEVEL_3": 0.6}

# Azure PdM (100 machines, hourly 2015) is the fleet backbone: machine N -> ELV-N.
ELEVATOR_MODELS = {
    "model1": "TRX-800 Traction (8 pax)",
    "model2": "TRX-1000 Traction (10 pax)",
    "model3": "MRL-1300 Machine-Room-Less (13 pax)",
    "model4": "HYD-600 Hydraulic (6 pax)",
}
MODEL_CAPACITY = {"model1": 8, "model2": 10, "model3": 13, "model4": 6}
SITES = ["Tower A", "Tower B", "Mall Central", "City Hospital", "Metro Station",
         "Tech Park 1", "Tech Park 2", "Residency North", "Residency South", "Airport T1"]

# Telemetry columns and the direction that indicates trouble.
SENSOR_MAP = {
    "volt": "motor_voltage_v",
    "rotate": "motor_rpm",
    "pressure": "brake_pressure_psi",
    "vibration": "car_vibration_mm_s",
}
SENSOR_DIRECTION = {
    "motor_voltage_v": "high",
    "motor_rpm": "low",
    "brake_pressure_psi": "high",
    "car_vibration_mm_s": "high",
}
SENSOR_CODE = {
    "motor_voltage_v": "S-VOLT",
    "motor_rpm": "S-RPM",
    "brake_pressure_psi": "S-PRESSURE",
    "car_vibration_mm_s": "S-VIBRATION",
}

ERROR_MAP = {"error1": "E101", "error2": "E102", "error3": "E103", "error4": "E104", "error5": "E105"}
COMPONENT_MAP = {"comp1": "DOOR", "comp2": "MOTOR", "comp3": "BRAKE", "comp4": "CONTROLLER"}
COMPONENTS = list(COMPONENT_MAP.values())

# AI4I 2020 failure modes reinterpreted as elevator drive faults.
AI4I_FAILURE_MAP = {"TWF": "W201", "HDF": "H301", "PWF": "P401", "OSF": "O501", "RNF": "R601"}
AI4I_USAGE = {"L": "Low traffic", "M": "Medium traffic", "H": "High traffic"}
OVERLOAD_FACTOR = 1.25  # max AI4I torque maps to 125% of the car's rated capacity (above 100% = overload)

SCHEDULED_MAINT_HOURS = 2.0
