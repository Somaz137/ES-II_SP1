from occupancy_rule import OccupancyRule


def make():
    return OccupancyRule(interval_s=10, confirm_s=120, fraction=0.75, hold_s=900)


def feed(rule, results, start=0, step=10):
    for i, result in enumerate(results):
        rule.add(result, start + i * step)


def entered_rule():
    """12 checks, 9 seen (misses at 20, 50, 80); last sighting at t=110."""
    rule = make()
    feed(rule, ["seen" if t not in (20, 50, 80) else "not_seen"
                for t in range(0, 120, 10)])
    return rule


def test_nine_of_twelve_enters():
    assert entered_rule().state(110)["state"] == "occupied"


def test_eight_of_twelve_does_not_enter():
    rule = make()
    feed(rule, ["seen" if t not in (20, 40, 50, 80) else "not_seen"
                for t in range(0, 120, 10)])
    s = rule.state(110)
    assert s["state"] == "not_seen"
    assert s["seen"] == 8
    assert s["needed"] == 9


def test_short_visit_does_not_enter():
    rule = make()
    feed(rule, ["seen"] * 6 + ["not_seen"] * 6)
    assert rule.state(110)["state"] == "not_seen"


def test_window_must_be_full():
    rule = make()
    feed(rule, ["seen"] * 6)
    assert rule.state(50)["state"] == "not_seen"


def test_hold_survives_missed_checks():
    rule = entered_rule()
    feed(rule, ["not_seen"] * 89, start=120)  # t=120..1000
    s = rule.state(1000)
    assert s["state"] == "occupied"
    assert s["held"] is True
    assert s["last_seen_at"] == 110


def test_hold_ends_after_900_s():
    rule = entered_rule()
    feed(rule, ["not_seen"] * 90, start=120)  # t=120..1010
    assert rule.state(1010)["state"] == "not_seen"


def test_camera_failure_keeps_hold_then_unknown():
    rule = entered_rule()
    feed(rule, ["failed"] * 89, start=120)  # t=120..1000
    s = rule.state(1000)
    assert s["state"] == "occupied"
    assert s["camera_working"] is False
    rule.add("failed", 1010)
    assert rule.state(1010)["state"] == "unknown"


def test_failed_camera_before_entry_is_unknown():
    rule = make()
    feed(rule, ["failed"] * 5)
    assert rule.state(40)["state"] == "unknown"


def test_no_checks_is_unknown():
    assert make().state(0)["state"] == "unknown"


def test_bounded_memory():
    rule = make()
    feed(rule, ["seen"] * 10000)
    assert len(rule._checks) <= 13


def test_assume_occupied_starts_hold():
    rule = make()
    rule.assume_occupied(0)
    feed(rule, ["not_seen"] * 88, start=10)  # t=10..880
    rule.add("not_seen", 890)
    s = rule.state(890)
    assert s["state"] == "occupied"
    assert s["held"] is True
    rule.add("not_seen", 900)
    assert rule.state(900)["state"] == "not_seen"


def test_sighting_after_assume_extends_hold():
    rule = make()
    rule.assume_occupied(0)
    feed(rule, ["not_seen"] * 29, start=10)  # t=10..290
    rule.add("seen", 300)
    feed(rule, ["not_seen"] * 80, start=310)  # t=310..1100
    assert rule.state(1100)["state"] == "occupied"
    feed(rule, ["not_seen"] * 10, start=1110)  # t=1110..1200
    assert rule.state(1200)["state"] == "not_seen"


def test_assume_is_not_a_check():
    rule = make()
    rule.assume_occupied(0)
    s = rule.state(0)
    assert s["state"] == "occupied"
    assert s["seen"] == 0
    assert s["checks"] == 0
    assert s["camera_working"] is False


def test_assume_earlier_than_last_sighting_keeps_later():
    rule = entered_rule()
    rule.assume_occupied(50)
    assert rule.state(110)["last_seen_at"] == 110


def test_state_reports_the_last_check_result_and_time():
    rule = make()
    assert rule.state(0)["last_result"] is None and rule.state(0)["last_check_at"] is None
    rule.add("seen", 10)
    rule.add("not_seen", 20)
    s = rule.state(25)
    assert s["last_result"] == "not_seen" and s["last_check_at"] == 20 and s["last_seen_at"] == 10
    rule.add("failed", 30)
    assert rule.state(30)["last_result"] == "failed"
