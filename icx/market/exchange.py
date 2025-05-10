import asyncio
import copy
from functools import reduce
from typing import Optional, TypeVar, Union
from datetime import datetime

import ccxt.pro as ccxt
import click
import plotext as plt
import pandas as pd

from .. import config, cui, log, util
from ..util import fvalue

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

def TS(v: int) -> datetime:
    # return datetime.fromtimestamp(v/1000, tz=util.UTC)
    return datetime.fromtimestamp(v/1000).astimezone()


class Base:
    @classmethod
    def format_fee(clz, fee: dict):
        if fee:
            return fvalue(float(fee["cost"]), '-', fee["currency"])
        else:
            return '-'

    @classmethod
    def fee(clz, x: dict):
        return Base.format_fee(x['fee'])


def monday(ts: datetime) -> bool:
    print(ts.hour)
    return ts.weekday() == 0
chart_label_config = {
    "1w": ("%Y-%m-%d", lambda ts: ts.day<=7 and (ts.month-1)%3 == 0),
    "1d": ("%Y-%m-%d", lambda ts: ts.day == 1),
    "4h": ("%Y-%m-%d %H:%M", lambda ts: (ts.weekday() == 0 and ts.hour//4 == 0) or (ts.weekday() == 3 and ts.hour//4 == 3)),
    "1h": ("%Y-%m-%d", lambda ts: ts.hour == 0),
    "30m": ("%Y-%m-%d %H:%M", lambda ts: ts.minute < 30 and ts.hour%12 == 0),
    "15m": ("%Y-%m-%d %H:%M", lambda ts: ts.minute < 15 and ts.hour%6 == 0),
    "1m": ("%Y-%m-%d %H:%M", lambda ts: ts.minute % 30 == 0),
}

async def show_market(conn: ccxt.Exchange, market: str, timeframe: str = "1h"):
    if timeframe not in chart_label_config:
        raise click.ClickException(f"Unknown timeframe={timeframe}")
    cnt = (plt.tw()-10)//2

    ticker, ohlcv, book = await asyncio.gather(
        conn.fetch_ticker(market),
        conn.fetch_ohlcv(market, timeframe, limit=cnt),
        conn.fetch_order_book(market),
    )
    show_chart(market, timeframe, ticker, ohlcv)
    show_orderbook(book)

def show_chart(market, timeframe, ticker, ohlcv):
    draw_chart(market, timeframe, ticker, ohlcv)
    plt.show()
    plt.clear_figure()

def render_chart(market, timeframe, ticker, ohlcv) -> str:
    draw_chart(market, timeframe, ticker, ohlcv)
    output = plt.build()
    plt.clear_figure()
    return output

def draw_chart(market, timeframe, ticker, ohlcv):
    title = '{market} / High:{high} / Last:{last} / Low:{low} / Avg:{average} / Interval:{timeframe}'.format(
        market=market, timeframe=timeframe, **ticker)

    height = max(plt.th()//2, min(30, plt.th()))
    
    df = pd.DataFrame(
        copy.deepcopy(ohlcv), columns=["datetime", "open", "high", "low", "close", "volume"]
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

    plt.hline(high, color='green')
    plt.hline(low, color='red')
    plt.hline(last)
    plt.text(str(high), x=mid_x, y=high, color='white', alignment='center')
    plt.text(str(low), x=mid_x, y=low, color='white', alignment='center')
    plt.text(str(last), x=mid_x, y=last, color='white', alignment='center')

    label_config = chart_label_config[timeframe]
    xticks = list(filter(lambda ts: label_config[1](TS(ts)), df['time']))
    xticklabels = [to_datetime(ts).strftime(label_config[0]) for ts in xticks]
    plt.xticks(xticks, xticklabels)
    for tick in xticks:
        plt.vertical_line(tick, color='gray')
    plt.grid()

def draw_orderbook(book: dict):
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

def render_orderbook(book: dict):
    draw_orderbook(book)
    output = plt.build()
    plt.clear_figure()
    return output

def show_orderbook(book: dict):
    draw_orderbook(book)
    plt.show()
    plt.clear_figure()

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


async def get_assets(exchanges: list[ccxt.Exchange]) -> dict:
    exchanges = [x for x in exchanges if x.has.get("fetchBalance", False)]

    if len(exchanges) == 0:
        return {}

    async def fetch_balance(exchange: ccxt.Exchange):
        balance = await exchange.fetch_balance()
        return (exchange.id, balance)

    balances = await asyncio.gather(*[
        asyncio.create_task(fetch_balance(exchange)) for exchange in exchanges
    ])
    return dict(balances)


class Asset(Base):
    cols = [
        cui.Column(lambda x, n: n, 5, "{:^5s}", "Currency"),
        cui.Column(lambda x, n: fvalue(x["free"],'-'), 15, "{:>}", "Free"),
        cui.Column(lambda x, n: fvalue(x["used"],'-'), 15, "{:>}", "Used"),
        cui.Column(lambda x, n: fvalue(x["total"],'-'), 15, "{:>}", "Total"),
    ]


async def show_assets(exchanges: list[ccxt.Exchange], raw: bool = False):
    assets = await get_assets(exchanges)
    if raw:
        util.dump_json(assets)
        return
    p = cui.RowPrinter(Asset.cols)
    for name, asset in assets.items():
        p.print_spanned(0, 4, [name.upper()], reverse=True, underline=True)
        p.print_header()
        for base in asset["free"].keys():
            v = asset[base]
            if v["total"] == 0:
                continue
            p.print_data(v, base, underline=True)


@main.command('asset', help='List available assets')
@click.argument("exchange", type=click.STRING, metavar="<exchange>", required=False)
@click.option("--raw", "-r", is_flag=True, default=False)
@run_async
async def exchange_asset(exchange: str, raw: bool = False):
    async with ExchangeList.get(exchange) as exchanges:
        await show_assets(exchanges)


async def exchange_sell_deposit(conn: ccxt.Exchange, market: str):
    base = conn.markets[market]['base']
    timestamp: int = None
    finished: list = []
    console: log.Console = log.console
    async def wait_next():
        with console.status('Sleep 60 seconds for the next check...'):
            await asyncio.sleep(60)

    async def wait_ready():
        with console.status('Sleep 5 seconds for finishing deposit...'):
            await asyncio.sleep(5)

    while True:
        with console.status('Fetch deposits ...'):
            deposits = await conn.fetch_deposits(base, since=timestamp)

        if timestamp is None:
            timestamp = max(deposits, key=lambda d: d["timestamp"])['timestamp']
            console.log(f'Waits for the deposits since {dt(timestamp)}')
            await wait_next()
            continue

        new_items = list(filter(lambda d: d['timestamp'] > timestamp, deposits))

        if len(new_items) == 0:
            await wait_next()
            continue

        unfinished = list(filter(lambda d: d['id'] not in finished, new_items))

        if len(unfinished) == 0:
            timestamp = max(new_items, key=lambda d: d["timestamp"])['timestamp']
            finished.clear()
            console.log(f'Waits for the deposits since {dt(timestamp)}')
            await wait_next()
            continue

        ready = list(filter(lambda d: d['status'] == 'ok', unfinished))

        if len(ready) == 0:
            await wait_ready()
            continue

        for item in ready:
            with console.status(f'Sell deposit {Deposit.amount(item)} at {dt(item["timestamp"])}'):
                console.log(f'Start to sell {Deposit.amount(item)} depositted at {dt(item["timestamp"])}')
                order = await conn.create_order(market, 'market', 'sell', item['amount'])
                console.log(f'The order is CREATED id={order["id"]}')
                while True:
                    order_detail = await conn.fetch_order(order['id'])
                    if order_detail['status'] == 'closed':
                        console.log(f'The order is CLOSED')
                        finished.append(item['id'])
                        break
                    await asyncio.sleep(1)


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
            log.info('You have {}'.format(fvalue(available, 'none', base)))
            return

        if amount == "all":
            amount_value = available
        elif amount == 'deposit':
            await exchange_sell_deposit(conn, market)
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

        log.info(f'Order created market={conn.id}/{market} amount={amount_value} price={price or "market"}', highlight=True)
        log.print(order["id"])

def to_datetime(v: Union[int, str, datetime]) -> datetime:
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        v = int(v, 0)
    elif not isinstance(v, int):
        v = int(v)
    return datetime.fromtimestamp(v/1000).astimezone()

def dt(v: Union[int, str, datetime]) -> str:
    return to_datetime(v).strftime('%Y-%m-%d %H:%M')

class Order(Base):
    keyword_styles: dict[str, dict] = {
        'buy': dict(fg='bright_green', bold=True),
        'sell': dict(fg='bright_red', bold=True),
        'closed': dict(dim=True),
        'open': dict(fg='yellow'),
    }

    BUY = cui.Styled('BUY', fg='bright_green', bold=True)
    SELL = cui.Styled('SELL', fg='bright_red', bold=True)

    @classmethod
    def side(clz, x: dict) -> any:
        if x['side'] == 'buy':
            return clz.BUY
        else:
            return clz.SELL

    OPEN = cui.Styled('OPEN', fg='bright_yellow', bold=True, reverse=True)

    @classmethod
    def status(clz, x: dict) -> any:
        status = x['status']
        if status == 'open':
            return clz.OPEN
        return cui.Styled(status.upper(), bold=True, reverse=True)

    @staticmethod
    def amount(x: dict, currency: Optional[str] = None):
        return fvalue(x['amount'], '-', currency)

    @staticmethod
    def price(x: dict):
        if x['price']:
            return fvalue(x['price'])
        elif x['average']:
            return cui.Styled(fvalue(x['average']), fg='yellow')
        else:
            return '-'

    cols1 = [
        cui.Column(lambda x: x["exchange"], 10, "{:<10}", "Exchange"),
        cui.Column(lambda x: dt(x["timestamp"]), 16, "{:<16}", "Datetime"),
        cui.Column(lambda x: x["symbol"], 10, "{:^}", "Market"),
        cui.Column(lambda x: Order.amount(x), 10, "{:>}", "Amount"),
        cui.Column(lambda x: Order.price(x), 10, "{:>}", "Price"),
        cui.Column(lambda x: Order.status(x), 14, "{:^}", "Status"),
    ]
    cols2 = [
        cui.Column(lambda x: x["id"], 40, "{:<40}", 'ID', span=2),
        cui.Column(lambda x: Order.side(x), 4, "{:^}", "Side"),
        cui.Column(lambda x: fvalue(x["filled"], '-'), 10, "{:>}", "Filled"),
        cui.Column(lambda x: fvalue(x["cost"], '-'), 10, "{:>}", "Cost"),
        cui.Column(lambda x: Order.fee(x), 10, "{:>}", "Fee"),
    ]

    detail = [
        cui.Column(lambda x, _: dt(x["timestamp"]), 16, "{:<16}", "Datetime"),
        cui.Column(lambda x, _: x["symbol"], 10, "{:^}", "Market"),
        cui.Column(lambda x, _: Order.side(x), 4, "{:^}", "Side"),
        cui.Column(lambda x, m: fvalue(x['amount'], '', m['base']), 10, "{:>}", "Amount"),
        cui.Column(lambda x, m: fvalue(x["price"], '-', m['quote']), 10, "{:>}", "Price"),
        cui.Column(lambda x, m: fvalue(x['filled'], '-', m['base']), 10, "{:>}", "Filled"),
        cui.Column(lambda x, m: fvalue(x["cost"], '-', m['quote']), 10, "{:>}", "Cost"),
        cui.Column(lambda x, _: Order.fee(x), 10, "{:>}", "Fee"),
        cui.Column(lambda x, _: Order.status(x), 14, "{:^}", "Status"),
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

    @staticmethod
    def get(exchange: str = None) -> 'ExchangeList':
        configs = get_exchange_configs()
        if exchange is None:
            exchanges = [get_connection(name, cfg) for name, cfg in configs.items()]
        elif exchange in configs:
            exchanges = [get_connection(exchange, configs[exchange])]
        else:
            if exchange not in ccxt.exchanges:
                raise click.ClickException(f'Unknown exchange={exchange}')
            raise click.ClickException(f"Missing configuration for exchange={exchange}")
        if len(exchanges) == 0:
            raise click.ClickException(f'No configured exchagnes')
        return ExchangeList(exchanges)


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
@click.argument('operation', type=click.Choice(['cancel', 'show']),
                default='show', required=False, metavar='<operation>')
@click.option('--market', '-m', type=click.STRING, metavar='<market>')
@click.option('--raw', '-r', type=click.STRING, is_flag=True)
@run_async
async def exchange_order(exchange: str, id: str, market: str, raw: bool, operation: str):
    async with ExchangeList.get(exchange) as exchanges:
        if id is not None:
            conn: ccxt.Exchange = exchanges[0]

            if operation == 'show':
                order = await conn.fetch_order(id)
                if raw:
                    util.dump_json(order)
                else:
                    p = cui.MapPrinter(Order.detail)
                    p.print_separater()
                    p.print_header()
                    p.print_separater()
                    p.print_data(order, conn.markets[order['symbol']])
                    p.print_separater()
                return
            elif operation == 'cancel':
                order = await conn.fetch_order(id)
                if order['status'] != 'open':
                    raise click.ClickException('The order is not open')
                res = click.prompt('Cancel the order? (y/n)',
                                   default='y',
                                   type=click.Choice(['y', 'n']),
                                   err=True)
                if res == 'y':
                    await conn.cancel_order(id)
                return
            else:
                raise click.ClickException(f'Unhandled operation={operation}')

        kwargs = {}
        if market is not None:
            kwargs['symbol'] = market.upper()

        async def fetch_open_orders(conn, **kwargs):
            orders = await conn.fetch_open_orders(**kwargs)
            for order in orders:
                order['exchange'] = conn.id
            return orders

        async def fetch_closed_orders(conn, **kwargs):
            orders = await conn.fetch_closed_orders(**kwargs)
            for order in orders:
                order['exchange'] = conn.id
                if conn.id == 'upbit':
                    cost = float(order['info']['executed_funds'])
                    order['cost'] = cost
                    if not order['average']:
                        filled = float(order['info']['executed_volume'])
                        order['average'] = cost / filled

            return orders

        with log.console.status('Fetch orders...'):
            tasks = [asyncio.create_task(fetch_open_orders(conn, **kwargs)) for conn in exchanges]
            if market is None:
                exchanges = list(filter(lambda x: not feature(x,'spot','fetchClosedOrders','symbolRequired'), exchanges))
            tasks.extend([asyncio.create_task(fetch_closed_orders(conn, **kwargs)) for conn in exchanges])

            orders = []
            for as_completed in asyncio.as_completed(tasks):
                try :
                    result = await as_completed
                    orders.extend(result)
                except:
                    continue

        orders.sort(key=lambda x: x['timestamp'])

        if raw:
            util.dump_json(orders)
            return

        if len(orders) == 0:
            log.info(f'No orders')
            return

        p = cui.MultiRowPrinter([
            Order.cols1,
            Order.cols2,
            cui.Separater(),
        ])
        p.print_separater()
        p.print_header()
        p.print_separater()
        for order in orders:
            p.print_data(order)


class Deposit:
    @staticmethod
    def amount(x: dict) -> any:
        return fvalue(x['amount'], '-', x['currency'])
    
    @staticmethod
    def status(x: dict) -> any:
        status = x['status']
        if status == 'ok':
            return cui.Styled(status.upper(), fg='bright_green')
        else:
            return cui.Styled(status.upper(), fg='bright_red')

    @staticmethod
    def duration(x: dict) -> any:
        updated = x['updated']
        if updated is None:
            return '-'
        ts1 = datetime.fromtimestamp(x['timestamp']/1000).astimezone()
        ts2 = datetime.fromtimestamp(updated/1000).astimezone()
        return str(ts2-ts1)

    cols = [
        cui.Column(lambda x: x['exchange'], 8, "{:<8}", "Exchange"),
        cui.Column(lambda x: dt(x["timestamp"]), 16, "{:<16}", "Created"),
        cui.Column(lambda x: Deposit.duration(x), 10, "{:^10}", "Duration"),
        cui.Column(lambda x: Deposit.amount(x), 12, '{:>12}', 'Amount'),
        cui.Column(lambda x: Deposit.status(x), 8, "{:^}", "Status"),
    ]

@main.command('deposit', help="Show deposit history or addresses")
@click.argument("exchange", type=click.STRING, required=False, metavar='<exchange>')
@click.argument("currency", type=click.STRING, required=False, metavar="<currency>")
@click.option("--set", "-s", type=(str, str), multiple=True,
    metavar="<key> <value>",
    help="Set configuration value corresponding to the key",
)
@click.option('--raw', '-r', is_flag=True)
@run_async
async def exchange_deposit(exchange: str, currency: str, set: list[tuple[str, str]], raw: bool):
    async with ExchangeList.get(exchange) as exchanges:
        if currency is None:
            async def fetch_deposits(conn: ccxt.Exchange) -> list[dict]:
                deposits = await conn.fetch_deposits()
                for deposit in deposits:
                    deposit['exchange'] = conn.id
                return deposits

            deposits = []
            tasks = [asyncio.create_task(fetch_deposits(conn)) for conn in exchanges]
            for task_result in asyncio.as_completed(tasks):
                try:
                    result = await task_result
                    deposits.extend(result)
                except:
                    continue
            deposits.sort(key=lambda x: x['timestamp'])

            if raw:
                # util.dump_json(deposits)
                log.print_json(deposits)
                return

            if len(deposits) == 0:
                log.info('There is not deposits')
                return

            p = cui.RowPrinter(Deposit.cols)
            p.print_separater()
            p.print_header()
            p.print_separater()
            for deposit in deposits:
                p.print_data(deposit)
            p.print_separater()
            return

        conn = exchanges[0]

        if currency == 'all':
            if conn.has.get('fetchDepositAddresses', False):
                result = await conn.fetch_deposit_addresses()
                log.print_json(result)
            else:
                raise click.ClickException(f'{conn.name}) requires <currency> for a')
            return

        if conn.has.get("fetchDepositAddresses", False):
            result = await conn.fetch_deposit_addresses(currency.upper(), dict(set))
            addr_info = result[currency.upper()]
        elif conn.has.get("fetchDepositAddress", False):
            addr_info = await conn.fetch_deposit_address(currency.upper(), dict(set))
        else:
            raise click.ClickException(
                f"Exchange {exchange} does not support fetchDepositAddress"
            )
        if raw:
            log.print_json(addr_info)
            return
        click.echo(addr_info["address"])

async def watch_market(conn: ccxt.Exchange, market: str, timeframe='1h'):
    if timeframe not in chart_label_config:
        raise click.ClickException(f"Unknown timeframe={timeframe}")
    cnt = (plt.tw()-10)//2

    with log.console.status(f"Fetching information of {market}") as progress:
        ticker, ohlcv = await asyncio.gather(
            conn.fetch_ticker(market),
            conn.fetch_ohlcv(market, timeframe, limit=cnt),
        )
    plt.clear_terminal()
    chart = render_chart(market, timeframe, ticker, ohlcv)
    while True:
        order_book = await conn.watch_order_book(market, 20)
        book = render_orderbook(order_book)
        cui.tputs('cup', 0, 0)
        cui.cecho(chart, nl=False)
        cui.cecho(book, nl=False)

market_table = [
    cui.Column(lambda name, info: name, 20, name='Name'),
    cui.Column(lambda name, info: info['base'], 5, name='Base'),
    cui.Column(lambda name, info: info['quote'], 5, name='Quote'),
    cui.Column(lambda name, info: info['type'], 6, name='Type'),
]

@main.command('market', help='Market information or chart')
@click.argument("exchange", type=click.STRING, metavar="<exchange>")
@click.argument("market", type=click.STRING, metavar="<market>", required=False)
@click.argument("timeframe", type=click.STRING, metavar="<timeframe>", default='1h', required=False)
@click.option('typename', '--type', '-t', type=click.Choice(['spot', 'swap', 'future']), default=None,
              metavar='<type>', help='Type of market to search')
@click.option('--raw', '-r', is_flag=True)
@click.option('--watch', '-w', is_flag=True)
@run_async
async def exchange_market(exchange: str, market: str, timeframe: str = '1h', raw: bool = False, typename: str = None, watch: bool = False):
    async with get_connection(exchange) as conn:
        markets = await conn.load_markets()
        market = market.upper() if market is not None else None

        if market in markets:
            if raw:
                util.dump_json(markets[market])
                return
            if watch:
                await watch_market(conn, market, timeframe)
                return
            await show_market(conn, market, timeframe)
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
            if watch:
                await watch_market(conn, matched[0][0], timeframe)
            await show_market(conn, matched[0][0], timeframe)
            return

        p = cui.RowPrinter(market_table)
        p.print_separater()
        p.print_header()
        p.print_separater()
        for name, info in matched:
            p.print_data(name, info)
        p.print_separater()


@main.command('has', help='List available API list')
@click.argument("exchange", type=click.STRING, metavar="<exchange>")
@click.argument("key", type=click.STRING, metavar="<key>", required=False)
@run_async
async def exchange_cap(exchange: str, key: str):
    async with get_connection(exchange) as conn:
        caps = [k for k, v in filter(lambda v: v[1], conn.has.items())]
        if key is not None:
            caps = filter(lambda k: key.lower() in k.lower(), caps)
        click.echo('\n'.join(caps))


@main.command('prop', help='Property of the exchange object')
@click.argument("exchange", type=click.STRING, metavar="<exchange>")
@click.argument("key", type=click.STRING, metavar="<key>")
@click.option('--load', '-l', type=click.STRING, metavar="<function for load>")
@run_async
async def exchange_query(exchange: str, key: str, load: str):
    async with get_connection(exchange) as conn:
        if load is not None:
            if not hasattr(conn, load):
                raise click.ClickException(f'Unknown load function={load}')
            load_func = getattr(conn, load)
            await load_func()
        if not hasattr(conn, key):
            items = [k for k in dir(conn) if key in k]
            if len(items) == 0:
                raise click.ClickException(f'Unknown property name={key}')
            print("\n".join(items))
            return
        util.dump_json(getattr(conn, key))

class Withdrawal(Base):
    @staticmethod
    def value(x: dict):
        return fvalue(x["amount"], '-', x["currency"])

    OK = cui.Styled('OK', fg='bright_green', bold=True)

    @classmethod
    def status(clz, x: dict) -> any:
        status = x['status']
        if status == 'ok':
            return clz.OK
        return cui.Styled(status.upper(), fg='bright_yellow' , bold=True)

    cols1 = [
        cui.Column(lambda x: x["exchange"], 10, "{:<10}", "Exchange"),
        cui.Column(lambda x: dt(x["timestamp"]), 16, "{:<16}", "Datetime"),
        cui.Column(lambda x: Withdrawal.value(x), 20, "{:>}", "Value"),
        cui.Column(lambda x: Withdrawal.fee(x), 10, "{:>}", "Fee"),
        cui.Column(lambda x: Withdrawal.status(x), 10, "{:^}", "Status"),
    ]


async def fetch_withdrawals(conn: ccxt.Exchange) -> list[dict]:
    withdrawals: list[dict] =  await conn.fetch_withdrawals()
    return [{ **x, 'exchange': conn.id } for x in withdrawals]


async def show_withdrawals(exchanges: list[ccxt.Exchange], raw: bool = False):
    with log.console.status('Fetch asset history...'):
        tasks = [asyncio.create_task(fetch_withdrawals(conn)) for conn in exchanges]
        withdrawals = []
        for as_completed in asyncio.as_completed(tasks):
            try:
                result = await as_completed
                withdrawals.extend(result)
            except:
                continue
    withdrawals.sort(key=lambda x: x['timestamp'])
    if raw:
        log.print_json(withdrawals)
        return

    p = cui.RowPrinter(Withdrawal.cols1)
    p.print_header()
    p.print_separater()
    for w in withdrawals:
        p.print_data(w)
    p.print_separater()


@main.command('withdraw', help='Withdraw related operations')
@click.argument('exchange', type=click.STRING, metavar='<exchange>', required=False)
@click.argument('currency', type=click.STRING, metavar='<currency>', required=False)
@click.argument('amount', type=click.STRING, metavar='<amount>', required=False)
@click.argument('address', type=click.STRING, metavar='<address>', required=False)
@click.option("--raw", "-r", is_flag=True, default=False)
@click.option('--param', '-p', type=(str,str), multiple=True)
@run_async
async def exchange_withdraw(
    exchange: str,
    currency: str,
    amount: str,
    address: str,
    raw: bool,
    param: list[tuple[str, str]]
):
    """Withdraw related operations

    Example:

    * `icx exchange withdraw <exchange> <currency> <amount> <address>`: Withdraw asset
    * `icx exchange withdraw <exchange> <currency>`: Show withdrawable amount
    * `icx exchange withdraw <exchange>`: Show withdraw history
    """
    async with ExchangeList.get(exchange) as exchanges:
        if currency is None:
            show_withdrawals(exchanges, raw)
            return

        conn: ccxt.Exchange = exchanges[0]
        assets = await get_assets([conn])
        if conn.id not in assets:
            raise click.ClickException(f"Unavailable asset information for exchange={conn.id}")

        currency = currency.upper()
        asset: dict = assets[conn.id].get(currency, None)
        if asset is None:
            raise click.ClickException(f"Unknown currency={currency}")

        if amount is None:
            if raw:
                util.dump_json(asset)
            else:
                p = cui.MapPrinter(Asset.cols)
                p.print_header()
                p.print_data(asset, currency, underline=True)
            return
        
        params = dict(param)
        if amount.lower() in ['all', 'max']:
            res = conn.withdraw(currency, asset["free"], address, params=params)
        else:
            res = conn.withdraw(currency, float(amount), address, params=params)
        log.print_json(res)
