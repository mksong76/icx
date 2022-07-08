#!/usr/bin/env python3

import json
import getpass
import os

from iconsdk.wallet.wallet import Wallet, KeyWallet

class MyWallet(Wallet):
    def __init__(self, file: str, password: str = None) -> None:
        self.file = file
        kstore = json.load(open(self.file, 'rb'))
        if 'address' not in kstore:
            raise Exception("InvalidKeyStore(NoAddress)")
        self.__addr = kstore['address']
        self.__wallet = None
        self.__password = password

    def __get_loaded(self) -> Wallet:
        if self.__wallet is None:
            if self.__password is None:
                password = getpass.getpass(prompt="WalletPassword:")
            else:
                password = self.__password
            self.__wallet = KeyWallet.load(self.file, password)
        return self.__wallet
    
    def get_address(self) -> str:
        return self.__addr

    def sign(self, data: bytes) -> bytes:
        return self.__get_loaded().sign(data)

    address = property(get_address)
    loaded = property(__get_loaded)

KEY_STORE_ENV="GOLOOP_RPC_KEY_STORE"
KEY_PASS_ENV="GOLOOP_RPC_KEY_PASSWORD"
cached_wallet = {}
def get_instance(ks: str = None, kp: str = None) -> MyWallet:
    global cached_wallet
    if ks is None:
        ks = os.getenv(KEY_STORE_ENV)
        kp = os.getenv(KEY_PASS_ENV)
    if ks is None:
        raise Exception(f'KeyStoreIsNotSpecified')

    if ks not in cached_wallet:
        wallet = MyWallet(ks, kp)
        cached_wallet[ks] = wallet
    return cached_wallet[ks]
