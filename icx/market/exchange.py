import asyncio
import json
import sys
from functools import reduce
from typing import Optional, TypeVar, Union
from datetime import datetime

import ccxt.async_support as ccxt
import click
import plotext as plt
import pandas as pd

from .. import config, cui, log, util

CONTEXT_EXCHANGE_CONFIG = "exchange.credentials"

Callee = TypeVar("Callee")

def run_async(func: asyncio.Future[Callee]) -> Callee:
    def async_caller(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))
    return async_caller

def exchange_as_conn(func: asyncio.Future[Callee]) -> Callee:
    def handle_async(exchange: str, *args, **kwargs):
        async def handle_exchange(*args, **kwargs):
            async with get_connection(exchange) as conn:
                return await func(conn, *args, **kwargs)
        return asyncio.run(handle_exchange(*args, **kwargs))
    return handle_async

@click.group("exchange", help="Exchange related operations")
@click.option("--auth", "-a", type=click.STRING, default=None,
    envvar="ICX_EXCHANGE_CONFIG",
    metavar="<exchanges.json>",
    help="Authentication credentials for the exchanges",
)
def main(auth: str):
    obj = click.get_current_context().obj
    if auth is not None and len(auth) > 0:
        obj[CONTEXT_EXCHANGE_CONFIG] = config.Config(auth)


def get_exchange(name: str, config: dict = None) -> ccxt.Exchange:
    if not hasattr(ccxt, name):
        raise click.ClickException(f"Unknown exchange name={name}")
    ex_class = getattr(ccxt, name)
    conn: ccxt.Exchange = ex_class(config) if config is not None else ex_class()
    conn.options["warnOnFetchOpenOrdersWithoutSymbol"] = False
    return conn


def get_exchange_configs(ctx: click.Context = None) -> dict:
    ctx = config.ensure_context(ctx)
    if CONTEXT_EXCHANGE_CONFIG in ctx.obj:
        return ctx.obj[CONTEXT_EXCHANGE_CONFIG]
    return {}


def get_connection(name: str, config: dict = None) -> ccxt.Exchange:
    if config is None:
        credentials = get_exchange_configs()
        if name in credentials:
            config = credentials[name]
    return get_exchange(name, config)

minute_ms = 60 * 1000
hour_ms = 60 * minute_ms
day_ms = 24 * hour_ms

# chart_label_config = {
#     "1d": ("%Y-%m-%d", 28 * day_ms),
#     "4h": ("%Y-%m-%d", 6*7 * 4 * hour_ms),
#     "1h": ("%Y-%m-%d", 24 * hour_ms),
#     "1m": ("%Y-%m-%d", 30 * minute_ms),
#     "15m": ("%Y-%m-%d %H:%M", 6 * 4 * 15 * minute_ms),
#     "30m": ("%Y-%m-%d %H:%M", 6 * 4 * 30 * minute_ms),
# }

def TS(v: int) -> datetime:
    return datetime.fromtimestamp(v/1000, tz=util.UTC)
    # return datetime.fromtimestamp(v/1000).astimezone()

def monday(ts: datetime) -> bool:
    print(ts.hour)
    return ts.weekday() == 0
chart_label_config = {
    "1w": ("%Y-%m-%d", lambda ts: ts.day<=7 and (ts.month-1)%3 == 0),
    "1d": ("%Y-%m-%d", lambda ts: ts.day == 1),
    "4h": ("%Y-%m-%d %H:%M", lambda ts: (ts.weekday() == 0 and ts.hour == 0) or (ts.weekday() == 3 and ts.hour == 12)),
    "1h": ("%Y-%m-%d", lambda ts: ts.hour == 0),
    "30m": ("%Y-%m-%d %H:%M", lambda ts: ts.minute < 30 and ts.hour%12 == 0),
    "15m": ("%Y-%m-%d %H:%M", lambda ts: ts.minute < 15 and ts.hour%6 == 0),
    "1m": ("%Y-%m-%d %H:%M", lambda ts: ts.minute % 30 == 0),
}

async def show_market(conn: ccxt.Exchange, market: str, interval: str = "1h"):
    if interval not in chart_label_config:
        raise click.ClickException(f"Unknown interval={interval}")

    # cnt = (plt.tw()-10)
    cnt = (plt.tw()-10)//2
    ticker, book, ohlcv = await asyncio.gather(
        conn.fetch_ticker(market),
        conn.fetch_order_book(market),
        conn.fetch_ohlcv(market, interval, limit=cnt),
    )

    title = '{market} / High:{high} / Last:{last} / Low:{low} / Avg:{average} / Interval:{interval}'.format(
        market=market, interval=interval, **ticker)

    height = max(plt.th()//2, min(30, plt.th()))
    label_config = chart_label_config[interval]
    df = pd.DataFrame(
        ohlcv, columns=["datetime", "open", "high", "low", "close", "volume"]
    )
    df.rename(columns={
        'datetime': 'time',
        'open':'Open',
        'high':'High',
        'low':'Low',
        'close':'Close'
    }, inplace=True)
    df.set_index('time')

    plt.plotsize(None, height)

    plt.theme('clear')
    plt.ticks_color('white+')
    plt.candlestick(df['time'], df)
    plt.title(title)

    last, high, low = ticker['last'], ticker['high'], ticker['low']
    mid_x = (df['time'].iloc[-1] + df['time'].iloc[0]) // 2

    plt.hline(last)
    plt.hline(high, color='green')
    plt.hline(low, color='red')
    plt.text(str(last), x=mid_x, y=last, color='white', alignment='center')
    plt.text(str(high), x=mid_x, y=high, color='white', alignment='center')
    plt.text(str(low), x=mid_x, y=low, color='white', alignment='center')

    xticks = list(filter(lambda ts: label_config[1](TS(ts)), df['time']))
    xticklabels = [pd.to_datetime(ts, unit='ms').strftime(label_config[0]) for ts in xticks]
    plt.xticks(xticks, xticklabels)
    for tick in xticks:
        plt.vertical_line(tick, color='gray')
    plt.grid()
    plt.show()
    plt.clear_figure()

    bar_labels = []
    bar_values = []
    bar_colors = []
    for order in reversed(book["asks"][:10]):
        bar_labels.append(order[0])
        bar_values.append(order[1])
        bar_colors.append("red")
    for order in book["bids"][:10]:
        bar_labels.append(order[0])
        bar_values.append(order[1])
        bar_colors.append("green")

    plt.theme('clear')
    plt.simple_bar(bar_labels, bar_values, color=bar_colors)
    plt.show()
    plt.clear_figure()

    return


@main.command("config", help="Manipulate exchange configurations")
@click.argument(
    "name", type=click.STRING, default=None, required=False, metavar="[<name>]"
)
@click.option(
    "--set",
    "-s",
    type=(str, str),
    multiple=True,
    metavar="<key> <value>",
    help="Set configuration value corresponding to the key",
)
@click.option("--delete", "-d", is_flag=True, default=False)
def exchange_config(name: str, set: list[tuple[str, str]], delete: bool):
    configs = get_exchange_configs()

    # Just listing configure exhchanges
    if name is None:
        if len(configs) == 0:
            log.info("No exchanges are configured", bold=True)
        else:
            log.info(f'Configured exchanges: {", ".join(configs.keys())}', bold=True)
        return

    if len(set) == 0:
        # If it's for deletion
        if delete:
            if name in configs:
                del configs[name]
                log.info(f"Remove configuration for {name}")
            else:
                log.warn(f"No configuration for {name}")
            return

        # Print the configuration
        if name in configs:
            util.dump_json(configs[name])
        else:
            log.warn(f"No configuration was set for {name}")
            if hasattr(ccxt, name):
                exchange_cls = getattr(ccxt, name)
                required = reduce(
                    lambda s, v: s + (v[0],) if v[1] else s,
                    exchange_cls.requiredCredentials.items(),
                    (),
                )
                log.debug(f"Required credentials: {required}")

        return

    conn = get_exchange(name)

    # Set the configuration of the exchange
    new_config = {}
    for key, value in set:
        if key not in conn.requiredCredentials:
            raise click.BadOptionUsage("set", f"Unknown key={key}")
        if not conn.requiredCredentials[key]:
            raise click.BadOptionUsage("set", f"{key} is not required")
        new_config[key] = value

    unsets = []
    for key, required in conn.requiredCredentials.items():
        if required and key not in new_config:
            unsets.append(key)
    if len(unsets) > 0:
        raise click.BadOptionUsage(
            "set", f'You must set the values of {", ".join(unsets)}'
        )

    configs[name] = new_config
    log.info(f"Update configuration for {name}")


@main.command("list", help="List available exchanges")
def exchange_list():
    for ex in ccxt.exchanges:
        print(ex)


@main.command('asset', help='List available assets')
@click.argument("names", type=click.STRING, nargs=-1, metavar="<name>")
@click.option("--raw", "-r", is_flag=True, default=False)
@run_async
async def exchange_asset(names: list[str], raw: bool):
    if len(names) == 0:
        names = get_exchange_configs().keys()
    if len(names) == 0:
        return

    p = cui.RowPrinter(
        [
            cui.Column(lambda x, n: n, 5, "{:^5s}", "Name"),
            cui.Column(lambda x, n: x["free"], 15, "{:>,g}", "Available"),
            cui.Column(lambda x, n: x["used"], 15, "{:>,g}", "Locked"),
            cui.Column(lambda x, n: x["total"], 15, "{:>,g}", "Total"),
        ]
    )
    accounts = {}
    async def fetch_balance(n: str):
        conn = get_connection(n)
        if not conn.has.get("fetchBalance", False):
            return
        balance = await conn.fetch_balance()
        accounts[n] = balance
        await conn.close()
    await asyncio.gather(*[fetch_balance(n) for n in names])

    if raw:
        util.dump_json(accounts)
        return

    for n, account in accounts.items():
        if len(account["free"].keys()) == 0:
            continue
        p.print_spanned(0, 4, [n.upper()], reverse=True, underline=True)
        p.print_header()
        for base in account["free"].keys():
            v = account[base]
            if v["total"] == 0:
                continue
            p.print_data(v, base, underline=True)


@main.command('sell', help='Sell currency')
@click.argument('exchange', type=click.STRING, metavar='<exchange>')
@click.argument('market', type=click.STRING, metavar='<market>', required=False)
@click.argument('amount', type=click.STRING, metavar='<amount>', required=False)
@click.argument('price', type=click.FLOAT, metavar='<price>', required=False)
@run_async
async def exchange_sell(
    exchange: str, market: str, amount: str, price: float):
    async with get_connection(exchange) as conn:
        _, balance = await asyncio.gather(conn.load_markets(), conn.fetch_balance())

        if market is None:
            bases = list(balance["free"].keys())
            log.info(f'Usable markets for your equities : {", ".join(list(bases))}')
            for market, market_info in conn.markets.items():
                if market_info["base"] in bases:
                    log.debug(
                        f'{market:<20} {click.style(market_info["type"], fg="green")}'
                    )
            return

        market = market.upper()
        if market not in conn.markets:
            raise click.ClickException(f"Unknown market={market}")

        market_info = conn.markets[market]
        base = market_info["base"]
        available = balance["free"].get(base, 0.0)

        if amount is None:
            await show_market(conn, market)
            log.info('You have {:,g} {}'.format(available, base))
            return

        if amount == "all":
            amount_value = available
        else:
            amount_value = float(amount)
        if amount_value > available:
            raise click.ClickException(
                f"Not enough {base} balance={available} amount={amount_value}"
            )

        if not conn.has.get("createOrder", False):
            raise click.ClickException(f"Exchange {exchange} does not support createOrder")

        if price is None:
            order = await conn.create_order(market, "market", "sell", amount_value)
        else:
            order = await conn.create_order(market, "limit", "sell", amount_value, price)

        click.secho(json.dumps(order, indent=2), dim=True, file=sys.stderr)
        click.echo(order["id"])

def fvalue(v: Optional[float], d: str = "") -> str:
    if v is None:
        return d
    else:
        return f'{v:,f}'

keyword_styles: dict[str, dict] = {
    'buy': dict(fg='bright_green', bold=True),
    'sell': dict(fg='bright_red', bold=True),
    'closed': dict(dim=True),
}

def kw(v: str) -> Union[str,cui.Styled]:
    return cui.Styled.wrap(v, keyword_styles.get(v.lower(), None))

def dt(v: int) -> str:
    ts = datetime.fromtimestamp(v/1000).astimezone()
    return ts.strftime('%Y-%m-%d %H:%M')

order_table = [
    # cui.Header(lambda x: x["id"], 40, "{:<40}", "ID"),
    cui.Header(lambda x: dt(x["timestamp"]), 16, "{:<16}", "Datetime"),
    cui.Column(lambda x: x["symbol"], 10, "{:^}", "Market"),
    cui.Column(lambda x: kw(x["side"].upper()), 4, "{:^}", "Side"),
    cui.Column(lambda x: fvalue(x["amount"]), 14, "{:>}", "Amount"),
    cui.Column(lambda x: fvalue(x["price"], '-'), 14, "{:>}", "Price"),
    cui.Column(lambda x: kw(x["status"].upper()), 14, "{:^}", "Status"),
]

class ExchangeList(list):
    def __new__(cls, *args):
        return super().__new__(cls, *args)

    async def __aenter__(self):
        for x in self:
            await x.__aenter__()
        return self

    async def __aexit__(self, *args):
        for x in self:
            await x.__aexit__(*args)

def feature(conn: ccxt.Exchange, *args) -> bool:
    obj: any = conn.features
    for arg in args:
        if arg in obj:
            obj = obj[arg]
        else:
            return None
    return obj

@main.command('order', help='Query order of the exchange')
@click.argument('exchange', type=click.STRING, metavar='<exchange>', required=False)
@click.argument('id', type=click.STRING, metavar='<id>', required=False)
@click.option('--market', '-m', type=click.STRING, metavar='<market>')
@click.option('--closed', '-c', type=click.STRING, is_flag=True)
@click.option('--raw', '-r', type=click.STRING, is_flag=True)
@run_async
async def exchange_order(exchange: str, id: str, market: str, raw: bool, closed: bool):
    # exchanges: list[ccxt.Exchange] = None
    configs = get_exchange_configs()
    if exchange is None:
        exchanges = [get_connection(name, cfg) for name, cfg in configs.items()]
    elif exchange in configs:
        exchanges = [get_connection(exchange, configs[exchange])]
    else:
        if exchange not in ccxt.exchanges:
            raise click.ClickException(f'Unknown exchange={exchange}')
        raise click.ClickException(f"Missing configuration for exchange={exchange}")

    async with ExchangeList(exchanges) as exchanges:
        if len(exchanges) == 0:
            raise click.ClickException(f'No configured exchagnes')

        if id is not None:
            tasks = [asyncio.create_task(conn.fetch_order(id)) for conn in exchanges]
            for as_completed in asyncio.as_completed(tasks):
                try :
                    result = await as_completed
                    print(result)
                    return
                except:
                    continue
            raise click.ClickException(f'Unknown order id={id}')

        kwargs = {}
        if market is not None:
            kwargs['symbol'] = market.upper()

        tasks = [asyncio.create_task(conn.fetch_open_orders(**kwargs)) for conn in exchanges]
        if market is None:
            exchanges = list(filter(lambda x: not feature(x,'spot','fetchClosedOrders','symbolRequired'), exchanges))
        tasks.extend([asyncio.create_task(conn.fetch_closed_orders(**kwargs)) for conn in exchanges])

        orders = []
        for as_completed in asyncio.as_completed(tasks):
            try :
                result = await as_completed
                orders.extend(result)
            except:
                continue

        if raw:
            util.dump_json(orders)
            return

        if len(orders) == 0:
            log.info(f'No orders')
            return

        p = cui.RowPrinter(order_table)
        p.print_separater()
        p.print_header()
        p.print_separater()
        for order in orders:
            p.print_data(order)
        p.print_separater()
        return


@main.command('deposit', help="Information for depositting currency to the exchange")
@click.argument("exchange", type=click.STRING, metavar="<exchange>")
@click.argument("currency", type=click.STRING, metavar="<currency>")
@click.option(
    "--set",
    "-s",
    type=(str, str),
    multiple=True,
    metavar="<key> <value>",
    help="Set configuration value corresponding to the key",
)
@run_async
async def exchange_deposit(exchange: str, currency: str, set: list[tuple[str, str]]):
    async with get_connection(exchange) as conn:
        # print("\n".join([k for k, v in filter(lambda v: v[1], conn.has.items())]))
        if conn.has.get("fetchDepositAddresses", False):
            address = await conn.fetch_deposit_addresses(currency.upper(), dict(set))
            click.secho(json.dumps(address, indent=2), dim=True, file=sys.stderr)
            click.echo(address[currency.upper()]["address"])
        elif conn.has.get("fetchDepositAddress", False):
            address = await conn.fetch_deposit_address(currency.upper(), dict(set))
            click.secho(json.dumps(address, indent=2), dim=True, file=sys.stderr)
            click.echo(address["address"])
        else:
            raise click.ClickException(
                f"Exchange {exchange} does not support fetchDepositAddress"
            )

exchagne_table = [
    cui.Column(lambda name, info: name, 20, name='Name'),
    cui.Column(lambda name, info: info['base'], 5, name='Base'),
    cui.Column(lambda name, info: info['quote'], 5, name='Quote'),
    cui.Column(lambda name, info: info['type'], 6, name='Type'),
]

@main.command('market', help='Market information or chart')
@click.argument("exchange", type=click.STRING, metavar="<exchange>")
@click.argument("market", type=click.STRING, metavar="<market>", required=False)
@click.argument("interval", type=click.STRING, metavar="<interval>", default='1h', required=False)
@click.option('typename', '--type', '-t', type=click.Choice(['spot', 'swap', 'future']), default=None,
              metavar='<type>', help='Type of market to search')
@click.option('--raw', '-r', type=click.STRING, is_flag=True)
@run_async
async def exchange_market(exchange: str, market: str, interval: str = '1h', raw: bool = False, typename: str = None):
    async with get_connection(exchange) as conn:
        markets = await conn.load_markets()
        market = market.upper() if market is not None else None

        if market in markets:
            if raw:
                util.dump_json(markets[market])
                return
            await show_market(conn, market, interval)
            return

        matched = markets.items()
        if market is not None:
            matched = list(filter(lambda k: market in k[0], matched))
        if typename is not None:
            matched = list(filter(lambda k: typename in k[1]['type'], matched))

        if len(matched) == 0:
            raise click.ClickException(f'No market matches with {market}')

        if raw:
            util.dump_json(dict(matched))
            log.info(f'Found {len(matched)} markets matches with {market}')
            return

        if len(matched) == 1:
            await show_market(conn, matched[0][0], interval)
            return

        p = cui.RowPrinter(exchagne_table)
        p.print_separater()
        p.print_header()
        p.print_separater()
        for name, info in matched:
            p.print_data(name, info)
        p.print_separater()


@main.command('has', help='List available feature list')
@click.argument("exchange", type=click.STRING, metavar="<exchange>")
@click.argument("key", type=click.STRING, metavar="<key>", required=False)
@run_async
async def exchange_cap(exchange: str, key: str):
    async with get_connection(exchange) as conn:
        caps = [k for k, v in filter(lambda v: v[1], conn.has.items())]
        if key is not None:
            caps = filter(lambda k: key in k, caps)
        click.echo('\n'.join(caps))


@main.command('query', help='Query property of the exchange')
@click.argument("exchange", type=click.STRING, metavar="<exchange>")
@click.argument("key", type=click.STRING, metavar="<key>", required=False)
@run_async
async def exchange_query(exchange: str, key: str):
    async with get_connection(exchange) as conn:
        if not hasattr(conn, key):
            raise click.ClickException(f'Unknown property name={key}')
        util.dump_json(getattr(conn, key))
