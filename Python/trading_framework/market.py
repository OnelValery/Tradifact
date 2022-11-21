import dateutil.tz
import datetime
import pandas as pd


def tz_filter(timezone_id):
    # timezones are evil, CST is not recognized, so special cases here
    if timezone_id == "CST":
        return "America/Chicago"
    return timezone_id


def parse_hours(hours, market_tz):
    day_fields = hours.split(";")
    intervals = []
    for day_field in day_fields:
        if "CLOSED" in day_field:
            continue
        day, *rest = day_field.split(":")
        if len(rest) != 1:
            # format for looks like this
            # we assume they could be more than one, separated by ","
            # 20180506:0005-20180506:2358;20180507:0005-20180507:2358;
            for interval_string in day_field.split(","):
                start, end = interval_string.split("-")
                dt_start = pd.to_datetime(start, format="%Y%m%d:%H%M")
                dt_start = dt_start.replace(tzinfo=market_tz)
                dt_end = pd.to_datetime(end, format="%Y%m%d:%H%M")
                dt_end = dt_end.replace(tzinfo=market_tz)
                if dt_start > dt_end:
                    dt_start = dt_start - datetime.timedelta(days=1)
                intervals.append((dt_start, dt_end))
        else:
            for interval_string in rest[0].split(","):
                start, end = interval_string.split("-")
                # start and stop are HHMM, we combine them with the day and parse them
                dt_start = pd.to_datetime(day + start, format="%Y%m%d%H%M")
                dt_start = dt_start.replace(tzinfo=market_tz)
                dt_end = pd.to_datetime(day + end, format="%Y%m%d%H%M")
                dt_end = dt_end.replace(tzinfo=market_tz)
                if dt_start > dt_end:
                    dt_start = dt_start - datetime.timedelta(days=1)
                intervals.append((dt_start, dt_end))
    days = []
    for start, end in intervals:
        days.append(start.date())
        days.append(end.date())
    return set(days), intervals


def market_open_at_time(dt, details, extended=False):
    market_tz = dateutil.tz.gettz(tz_filter(details.timeZoneId))
    hours = details.tradingHours if extended else details.liquidHours
    (days, intervals) = parse_hours(hours, market_tz)
    for start, end in intervals:
        if start <= dt <= end:
            return True
    return False


def market_open_at_date(date, details, extended=False):
    market_tz = dateutil.tz.gettz(tz_filter(details.timeZoneId))
    hours = details.tradingHours if extended else details.liquidHours
    (days, intervals) = parse_hours(hours, market_tz)
    for start, end in intervals:
        if start.date() == date or end.date() == date:
            return True
    return False


def market_close_time(date, details, extended=False):
    market_tz = dateutil.tz.gettz(tz_filter(details.timeZoneId))
    hours = details.tradingHours if extended else details.liquidHours
    (days, intervals) = parse_hours(hours, market_tz)
    close_time = None
    for start, end in intervals:
        if end.date() == date:
            close_time = end
    return close_time


def market_open_time(date, details, extended=False):
    market_tz = dateutil.tz.gettz(tz_filter(details.timeZoneId))
    hours = details.tradingHours if extended else details.liquidHours
    (days, intervals) = parse_hours(hours, market_tz)
    open_time = None
    for start, end in reversed(intervals):
        if start.date() == date:
            open_time = start
    return open_time
