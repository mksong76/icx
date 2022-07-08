#!/usr/bin/env python3

import json
import click
import re

from . import util, service

def type_to_str(item: dict) -> str:
    result = ''
    if 'name' in item:
        if 'default' in item:
            result = click.style(item['name'], dim=True)+":"
        else:
            result = f'{item["name"]}:'
    tn: str = item['type']
    result += click.style(tn, fg='green', bold=True)
    if tn.endswith('struct'):
        items = []
        for field in item['fields']:
            items.append(type_to_str(field))
        result += '{'+(','.join(items))+'}'
    if 'default' in item:
        default = item['default']
        if default is not None:
            result += f'={default}'
    return result

def outputs_to_str(outputs: list) -> str:
    if len(outputs) == 0:
        return None
    else:
        items = []
        for output in outputs:
            items.append(type_to_str(output))
        if len(items) > 1:
            return f'({",".join(items)})'
        else:
            return items[0]

def api_entry_to_str(entry: dict) -> str:
    tn = entry['type']
    if tn == 'function':
        items = []

        if 'readonly' in entry and entry['readonly'] == '0x1':
            items.append(click.style('readonly', fg='yellow', bold=True))
        else:
            items.append(click.style('writable', fg='red', bold=True))

        inputs = []
        for input in entry['inputs']:
            inputs.append(type_to_str(input))
        name = click.style(entry['name'], bold=True, fg='cyan')
        items.append(f'{name}({", ".join(inputs)})')

        output = outputs_to_str(entry['outputs'])
        if output is not None:
            items += ['->', output]

        return " ".join(items)
    elif tn == 'eventlog':
        items = []
        items.append(click.style('eventlog', bold=True))
        name = click.style(entry['name'], bold=True, fg='cyan')
        inputs = []
        for input in entry['inputs']:
            inputs.append(type_to_str(input))
        items.append(f'{name}({",".join(inputs)})')
        return " ".join(items)
    else:
        return json.dumps(entry)

def dumps(entries: list, sep: str = '\n') -> str:
    api_entries = []
    for entry in entries:
        api_entries.append(api_entry_to_str(entry))
    return str(sep).join(api_entries)


@click.command('apis')
@click.argument('addr')
@click.option('--raw', '-r', type=bool, is_flag=True)
@click.option('--filter', '-f', type=str, default=None)
def get_apis(addr: str, raw: bool = False, filter: str = None):
    svc = service.get_instance()
    api = svc.get_score_api(util.ensure_address(addr))
    if filter is not None:
        regex = re.compile(filter)
        new_api = []
        for entry in api:
            if regex.match(entry['name']):
                new_api.append(entry)
        api = new_api
    if raw:
        print(json.dumps(api, indent=2))
    else:
        print(dumps(api))
