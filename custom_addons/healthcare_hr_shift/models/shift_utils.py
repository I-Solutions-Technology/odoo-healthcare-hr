"""Pure time helpers shared by shifts, attendance and allowances.

All datetimes entering or leaving these helpers are naive UTC (Odoo storage format).
Local computations use the given pytz timezone so DST and midnight crossing are correct.
"""
from datetime import datetime, time, timedelta

import pytz


def float_to_time(value):
    """8.5 -> time(8, 30); 24.0 -> time(0, 0)."""
    value = value % 24
    hours = int(value)
    minutes = int(round((value - hours) * 60))
    if minutes == 60:
        hours, minutes = hours + 1, 0
    return time(hours % 24, minutes)


def get_tz(name):
    try:
        return pytz.timezone(name or 'UTC')
    except pytz.UnknownTimeZoneError:
        return pytz.utc


def local_to_utc(naive_local, tz):
    return tz.localize(naive_local, is_dst=False).astimezone(pytz.utc).replace(tzinfo=None)


def utc_to_local(naive_utc, tz):
    return pytz.utc.localize(naive_utc).astimezone(tz).replace(tzinfo=None)


def shift_interval(on_date, start_float, duration_hours, tz):
    """UTC interval of a shift starting at ``start_float`` local time on ``on_date``."""
    local_start = datetime.combine(on_date, float_to_time(start_float))
    start = local_to_utc(local_start, tz)
    return start, start + timedelta(hours=duration_hours)


def overlap_hours(a_start, a_end, b_start, b_end):
    start, end = max(a_start, b_start), min(a_end, b_end)
    return max((end - start).total_seconds() / 3600.0, 0.0)


def split_hours(start, end, tz, night_start=22.0, night_end=6.0, weekend_days=(5, 6), holidays=()):
    """Night / weekend / holiday hours inside [start, end] (naive UTC).

    :param weekend_days: python weekday numbers (Monday=0) considered weekend
    :param holidays: iterable of (start, end) naive UTC intervals
    :return: dict(night=, weekend=, holiday=)
    """
    result = {'night': 0.0, 'weekend': 0.0, 'holiday': 0.0}
    if not start or not end or end <= start:
        return result
    local_start, local_end = utc_to_local(start, tz), utc_to_local(end, tz)
    day = local_start.date() - timedelta(days=1)
    while day <= local_end.date():
        midnight = datetime.combine(day, time(0))
        # night window of this day (may cross midnight)
        n_start = midnight + timedelta(hours=night_start)
        n_end = midnight + timedelta(hours=night_end)
        if night_end <= night_start:
            n_end += timedelta(days=1)
        result['night'] += overlap_hours(start, end, local_to_utc(n_start, tz), local_to_utc(n_end, tz))
        if day.weekday() in weekend_days:
            result['weekend'] += overlap_hours(
                start, end, local_to_utc(midnight, tz), local_to_utc(midnight + timedelta(days=1), tz))
        day += timedelta(days=1)
    for h_start, h_end in holidays:
        result['holiday'] += overlap_hours(start, end, h_start, h_end)
    return {key: round(value, 2) for key, value in result.items()}
