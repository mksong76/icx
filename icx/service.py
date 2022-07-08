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

class Service(IconService):
    def __init__(self, provider: HTTPProvider):
        super().__init__(provider)

    def estimate_and_send_tx(self, tx: Transaction, wallet: Wallet) -> any:
        step_limit = self.estimate_step(tx) + 10_000
        signed_tx = SignedTransaction(tx, wallet, step_limit)
        tx_hash = self.send_transaction(signed_tx)

        for i in range(5):
            try :
                result = self.get_transaction_result(tx_hash=tx_hash)
            except:
                sleep(1.0)
                continue

            if result['status'] != 1:
                raise Exception(f'FAIL(failure={result["failure"]})')
            return result

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