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
    def __init__(self, provider: HTTPProvider):
        super().__init__(provider)

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
                sleep(1.0)
                continue

            if result['status'] != 1:
                raise TransactionFailure(tx_hash, result,
                    f'TransactionFail(failure={result["failure"]}')
            return result
        raise FailureAfterSend(tx_hash, f'Timeout(repeat={repeat})')

URI_ENV='GOLOOP_RPC_URI'
DEBUG_ENV='GOLOOP_DEBUG_URI'
cached_service = {}
def get_instance(url: str = None) -> Service:
    global cached_service

    if url is None:
        url = os.getenv(URI_ENV, MAINNET_URL)

    if url not in cached_service:
        service = Service(HTTPProvider(url))
        cached_service[url] = service
    return cached_service[url]