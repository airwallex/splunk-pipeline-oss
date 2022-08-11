from datetime import datetime
import pytz


def unix_time_millis(dt):
    epoch = datetime.utcfromtimestamp(0)
    aware = pytz.utc.localize(epoch)
    return int((dt - aware).total_seconds() * 1000.0)


def microseconds(dt):
    return int(unix_time_millis(dt) * 1000.0)
