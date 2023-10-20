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

time_modulators = [
    (1000,'µs'),
    (1000,'ms'),
    (60,'s'),
    (60,'m'),
    (24,'h'),
    (0,'d'),
]

def int_to_str_with_modulators(s: int, modulators: list, sep: str = '') -> str:
    ret = []
    for mod in modulators:
        if s == 0:
            if len(ret) == 0:
                ret.append(f'0{mod[1]}')
            break
        if mod[0] == 0:
            ret.append(f'{s}{mod[1]}')
            break
        v = s%mod[0]
        if v > 0:
            ret.append(f'{v}{mod[1]}')
        s = s//mod[0]
    ret.reverse()
    ret = ret[:2]
    return sep.join(ret)

def secs_to_str(s: int, /, **kwargs) -> str:
    if s<0:
        return '-'+secs_to_str(-s, **kwargs)
    return int_to_str_with_modulators(s, time_modulators[2:], **kwargs)

if __name__ == "__main__":
    for arg in sys.argv[1:]:
        print(time_to_ms(arg))