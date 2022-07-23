#!/usr/bin/env python3

from copy import deepcopy
import json
from typing import Iterator, MutableMapping
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

    def __len__(self) -> int:
        return self.__config.__iter__()

    def save(self) -> None:
        with click.open_file(self.__file, 'w') as fd:
            json.dump(self.__config, fd, indent=2)

if __name__ == '__main__':
    config = Config('config.json')
    config['puha'] = { 'test': 1 }

    config = Config('config.json')
    for k in config:
        print(k)
    for k, v in config.items():
        print(k, v)
