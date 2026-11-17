"""Bosch air-quality index state and word bands. A Bosch estimate, not a measurement of a gas."""

# bsec_datatypes.h (BSEC2 1.10.2610) describes IAQ accuracy 0 as "Stabilization / run-in
# ongoing", 1 as "Low accuracy", 2 as "Medium accuracy: auto-trimming ongoing" and 3 as
# "High accuracy". The project shows the index from accuracy 2. A project decision.
IAQ_MIN_ACCURACY = 2


def air_quality_state(iaq, accuracy, reading_current):
    """current, calibrating or unavailable. Only a current index may be shown as a value."""
    if not reading_current or accuracy is None:
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
