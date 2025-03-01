#!/usr/bin/env python3

from copy import deepcopy
import json
from typing import Iterator, MutableMapping
import os

import click

CONTEXT_CONFIG = "config"

class Config(MutableMapping):
    def __init__(self, file: str) -> None:
        self.__file = file
        try :
            with click.open_file(self.__file, 'r') as fd:
                self.__config = json.load(fd)
                if type(self.__config) is not dict:
                    self.__config = {}
        except:
            self.__config = {}

    def __getitem__(self, name: str) -> any:
        if name in self.__config:
            return deepcopy(self.__config[name])
        else:
            return {}

    def __setitem__(self, name: str, value: any) -> None:
        self.__config[name] = deepcopy(value)
        self.save()

    def __contains__(self, name) -> bool:
        return name in self.__config

    def __delitem__(self, name) -> None:
        del(self.__config, name)
        self.save()

    def __iter__(self) -> Iterator:
        return self.__config.__iter__()

    def items(self) -> Iterator:
        return self.__config.items()

    def __len__(self) -> int:
        return self.__config.__len__()

    def save(self) -> None:
        base_dir = os.path.dirname(self.__file)
        os.makedirs(base_dir, exist_ok=True, mode=0o700)

        opener = lambda name, flags: os.open(name, flags, 0o600)
        with open(self.__file, 'w', opener=opener) as fd :
            json.dump(self.__config, fd, indent=2)

    def __str__(self) -> str:
        return self.__config.__str__()

    def __repr__(self) -> str:
        return self.__config.__repr__()

def ensure_context(ctx: click.Context = None) -> click.Context:
    return ctx if ctx is not None else click.get_current_context()

def get_instance(ctx: click.Context = None) -> Config:
    return ensure_context(ctx).obj[CONTEXT_CONFIG]

if __name__ == '__main__':
    config = Config('config.json')
    config['puha'] = { 'test': 1 }

    config = Config('config.json')
    for k in config:
        print(k)
    for k, v in config.items():
        print(k, v)
