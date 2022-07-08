#!/usr/bin/env python3

import re
import sys

TIME_REGEX=re.compile(r'((?P<minute>[0-9.]+)m)?((?P<second>[0-9.]+)s)?((?P<milli>[0-9.]+)ms)?((?P<micro>[0-9.]+)µs)?')
def time_to_ms(s: str) -> float:
    m = TIME_REGEX.match(s)
    if not m:
        raise Exception(f"InvalidTimeFormat(s={s})")
    ts = 0.0
    minute = m.group('minute')
    if minute is not None:
        ts += float(minute)*60*1000
    second = m.group('second')
    if second is not None:
        ts += float(second)*1000
    milli = m.group('milli')
    if milli is not None:
        ts += float(milli)
    micro = m.group('micro')
    if micro is not None:
        ts += float(micro)/1000
    return ts

if __name__ == "__main__":
    for arg in sys.argv[1:]:
        print(time_to_ms(arg))