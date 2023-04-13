#!/usr/bin/env python3

import sys

def compare_list(vl1: list, vl2: list) -> int:
    max_cnt = max(len(vl1), len(vl2))
    for idx in range(max_cnt):
        if len(vl1) <= idx:
            return -1
        if len(vl2) <= idx:
            return 1
        if vl1[idx] < vl2[idx]:
            return -1
        if vl1[idx] > vl2[idx]:
            return 1
    return 0


def is_lower_version(v1: str, v2: str) -> bool:
    if v2 is None:
        return False
    if v1 is None:
        return True
    lst1 = v1.split('-')
    lst2 = v2.split('-')
    if lst1[0].startswith('v') and lst2[0].startswith('v'):
        try:
            vst1 = lst1[0][1:].split('.')
            vst2 = lst2[0][1:].split('.')
            vst1 = list(map((lambda a: int(a, 0)), vst1))
            vst2 = list(map((lambda a: int(a, 0)), vst2))
            result = compare_list(vst1, vst2)
            if result < 0:
                return True
            if result > 0:
                return False
            return compare_list(lst1[1:], lst2[1:]) < 0
        except BaseException as e:
            return v1 < v2
    else:
        return v1 < v2


if __name__ == '__main__':
    print(is_lower_version(sys.argv[1], sys.argv[2]))