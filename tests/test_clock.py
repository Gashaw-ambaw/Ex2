from datetime import date, datetime, timezone

import pytest

from app.clock import Clock


# "Aware" means the time carries its timezone. Set() lets a test freeze the time.
def test_now_is_utc_and_aware():
    now = Clock().now()
    assert now.tzinfo is not None
    assert now.utcoffset().total_seconds() == 0


def test_set_fixes_the_time():
    clock = Clock()
    clock.set(datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc))
    assert clock.now() == datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)
    assert clock.now_iso() == "2026-11-24T12:00:00+00:00"


def test_set_rejects_a_naive_time():
    with pytest.raises(ValueError):
        Clock().set(datetime(2026, 11, 24, 12, 0))


def test_israel_time_in_summer_is_utc_plus_3():
    clock = Clock()
    clock.set(datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc))
    assert clock.israel_now().hour == 15


def test_israel_time_in_winter_is_utc_plus_2():
    clock = Clock()
    clock.set(datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc))
    assert clock.israel_now().hour == 14


def test_today_is_the_israel_date():
    clock = Clock()
    # 22:30 UTC on 24/11 is 00:30 on 25/11 in Israel.
    clock.set(datetime(2026, 11, 24, 22, 30, tzinfo=timezone.utc))
    assert clock.today() == date(2026, 11, 25)
