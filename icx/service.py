#!/usr/bin/env python3


import os
from time import sleep

from iconsdk.builder.call_builder import CallBuilder
from iconsdk.builder.transaction_builder import CallTransactionBuilder
from iconsdk.icon_service import IconService, SignedTransaction, Transaction
from iconsdk.providers.http_provider import HTTPProvider
from iconsdk.wallet.wallet import KeyWallet, Wallet

from .util import CHAIN_SCORE

MAINNET_URL = 'https://ctz.solidwallet.io/api/v3'
MAINNET_NID = '0x1'


class FailureAfterSend(Exception):
    def __init__(self, tx_hash: str, *args: object) -> None:
        super().__init__(*args)
        self.__tx_hash = tx_hash

    @property
    def tx_hash(self) -> str:
        return self.__tx_hash


class TransactionFailure(FailureAfterSend):
    def __init__(self, tx_hash: str, result: dict, *args: object) -> None:
        super().__init__(tx_hash, *args)
        self.__result = result

    @property
    def result(self) -> dict:
        return self.__result


class Service(IconService):
    def __init__(self, provider: HTTPProvider, nid: int):
        super().__init__(provider)
        self.__nid = nid

    @property
    def nid(self) -> int:
        return self.__nid

    def send_transaction_and_pull(self, tx: SignedTransaction) -> any:
        try:
            result = self.send_transaction_and_wait(tx)
            return result
        except:
            pass
        tx_hash = self.send_transaction(tx)
        return self.pull_transaction_result(tx_hash)

    def estimate_and_send_tx(self, tx: Transaction, wallet: Wallet) -> any:
        step_limit = self.estimate_step(tx) + 10_000
        signed_tx = SignedTransaction(tx, wallet, step_limit)
        return self.send_transaction_and_pull(signed_tx)

    def pull_transaction_result(self, tx_hash: str, repeat: int = 5) -> any:
        for i in range(repeat):
            try :
                result = self.get_transaction_result(tx_hash=tx_hash)
            except:
                sleep(2.0)
                continue

            if result['status'] != 1:
                raise TransactionFailure(tx_hash, result,
                    f'TransactionFail(failure={result["failure"]}')
            return result
        raise FailureAfterSend(tx_hash, f'Timeout(repeat={repeat})')

cached_service = {}
default_net = None
def get_instance(url: str = None, nid: int = None) -> Service:
    global cached_service
    global default_net

    if url is None:
        if default_net is not None:
            url, nid = default_net
        else:
            url = os.getenv('GOLOOP_RPC_URI', MAINNET_URL)
            nid = int(os.getenv('GOLOOP_RPC_NID', MAINNET_NID), 0)

    if url not in cached_service:
        service = Service(HTTPProvider(url), nid)
        cached_service[url] = service
    return cached_service[url]

def set_default(url: str = None, nid: int = None):
    global default_net
    default_net = (url, str(nid))