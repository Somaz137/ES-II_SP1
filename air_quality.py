"""Bosch air-quality index state and word bands. A Bosch estimate, not a measurement of a gas."""

# bsec_datatypes.h (BSEC2 1.10.2610) describes IAQ accuracy 0 as "Stabilization / run-in
# ongoing", 1 as "Low accuracy", 2 as "Medium accuracy: auto-trimming ongoing" and 3 as
# "High accuracy". The project shows the index from accuracy 2. A project decision.
IAQ_MIN_ACCURACY = 2

# BME680 gas-sensor fault: on this module the gas element reads open-circuit whenever the
# heater is at temperature, so gas_ohms is 12917166 (float maths can give 12917167). Bench
# tests 2026-11-27/28. This many fresh readings in a row within the tolerance is a fault.
# It clears only after GAS_FAULT_CLEAR_READINGS fresh readings in a row outside the window: after
# a BME680 restart the first reading can be real while the heater is not yet hot.
GAS_FAULT_OHMS = 12917166
GAS_FAULT_TOLERANCE = 2
GAS_FAULT_READINGS = 3
GAS_FAULT_CLEAR_READINGS = 20
GAS_FAULT_MESSAGE = "Not available: gas sensor fault"


def gas_stuck(gas_ohms):
    """True when the gas resistance is within the tolerance of the open-circuit fault value."""
    if isinstance(gas_ohms, bool) or not isinstance(gas_ohms, (int, float)):
        return False
    return abs(gas_ohms - GAS_FAULT_OHMS) <= GAS_FAULT_TOLERANCE


def air_quality_state(iaq, accuracy, reading_current, gas_fault=False):
    """current, calibrating or unavailable. Only a current index may be shown as a value."""
    if gas_fault or not reading_current or accuracy is None:
        return "unavailable"
    if accuracy < IAQ_MIN_ACCURACY:
        return "calibrating"
    return "current" if iaq is not None else "unavailable"


def band_word(value, bands):
    """The word of the first entry whose up_to the value does not exceed; the last is open."""
    if value is None:
        return None
    for entry in bands:
        if "up_to" not in entry or value <= entry["up_to"]:
            return entry["word"]
    return None
