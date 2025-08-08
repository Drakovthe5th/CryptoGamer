import os
import time
import logging
import requests
import base64
import asyncio
from datetime import datetime, timedelta

from pytoniq import LiteClient
from pytoniq_core import begin_cell, Address
from pytoniq import WalletV4R2

# Config object from your project
from config import config

logger = logging.getLogger(__name__)

# --------------------- Robust tonsdk imports ---------------------
Wallets = None
WalletVersionEnum = None
_import_errs = []
try:
    from tonsdk.contract.wallet import Wallets as _Wallets, WalletVersionEnum as _WV
    Wallets, WalletVersionEnum = _Wallets, _WV
except Exception as e:
    _import_errs.append(("tonsdk.contract.wallet", e))
    try:
        from tonsdk.wallet import Wallets as _Wallets, WalletVersionEnum as _WV
        Wallets, WalletVersionEnum = _Wallets, _WV
    except Exception as e2:
        _import_errs.append(("tonsdk.wallet", e2))
        try:
            from tonsdk.contracts.wallet import Wallets as _Wallets, WalletVersionEnum as _WV
            Wallets, WalletVersionEnum = _Wallets, _WV
        except Exception as e3:
            _import_errs.append(("tonsdk.contracts.wallet", e3))

if Wallets is None or WalletVersionEnum is None:
    # do not raise here — we'll raise later if mnemonic path is required
    logger.debug("Could not import tonsdk Wallets/WalletVersionEnum. Import attempts: %s",
                 ", ".join(f"{p}: {type(ex).__name__}" for p, ex in _import_errs))


# --------------------- Helper: mnemonic -> keys/wallet ---------------------
def _build_wallet_from_mnemonic(mnemonic_list):
    """
    Try multiple Wallets.* factory signatures and normalize output to:
      (private_key_bytes_or_None, public_key_bytes_or_None, wallet_obj)
    Raises RuntimeError if none succeed or private key can't be extracted.
    """
    if Wallets is None:
        raise RuntimeError("tonsdk not available in the environment; install 'tonsdk' or provide TON_PRIVATE_KEY")

    attempts = []
    # gather possible callables depending on available methods
    if hasattr(Wallets, "from_mnemonics"):
        attempts.append(lambda: Wallets.from_mnemonics(mnemonic_list, WalletVersionEnum.v4r2, 0))
        attempts.append(lambda: Wallets.from_mnemonics(mnemonic_list, 0, WalletVersionEnum.v4r2))
    if hasattr(Wallets, "from_mnemonic"):
        attempts.append(lambda: Wallets.from_mnemonic(mnemonic_list, WalletVersionEnum.v4r2, 0))
        attempts.append(lambda: Wallets.from_mnemonic(mnemonic_list, 0, WalletVersionEnum.v4r2))

    last_exc = None
    for call in attempts:
        try:
            res = call()
        except Exception as e:
            last_exc = e
            continue

        wallet_obj = None
        private_key = None
        public_key = None

        # If the factory returned a tuple/list, try to pick wallet_obj and private key from it
        if isinstance(res, (tuple, list)):
            # common shapes observed:
            # (wallet_obj, mnemonic_words)
            # (private_key_bytes, wallet_obj)
            # (wallet_obj, something_else)
            # (wallet_obj, mnemonic_words, ...)
            # try to detect wallet_obj first
            for item in res:
                if hasattr(item, "address") or hasattr(item, "private_key") or hasattr(item, "public_key") or hasattr(item, "keypair"):
                    wallet_obj = item
                    break

            # if wallet_obj not found, maybe the tuple is (private_key, wallet_obj)
            if wallet_obj is None and len(res) >= 2:
                if isinstance(res[0], (bytes, bytearray)) and (hasattr(res[1], "address") or hasattr(res[1], "private_key")):
                    private_key = res[0]
                    wallet_obj = res[1]

            # case: (private_key_bytes, public_key_bytes)
            if wallet_obj is None and len(res) >= 2 and isinstance(res[0], (bytes, bytearray)) and isinstance(res[1], (bytes, bytearray)):
                private_key = res[0]
                public_key = res[1]

        else:
            # single object returned (wallet instance typical)
            wallet_obj = res

        # If we found wallet_obj, try to extract keys
        if wallet_obj is not None:
            # direct attrs
            if private_key is None and hasattr(wallet_obj, "private_key"):
                private_key = getattr(wallet_obj, "private_key")
            if public_key is None and hasattr(wallet_obj, "public_key"):
                public_key = getattr(wallet_obj, "public_key")

            # some versions expose keypair tuple
            if (private_key is None or public_key is None) and hasattr(wallet_obj, "keypair"):
                kp = getattr(wallet_obj, "keypair")
                if isinstance(kp, (tuple, list)):
                    if private_key is None and len(kp) >= 1:
                        private_key = kp[0]
                    if public_key is None and len(kp) >= 2:
                        public_key = kp[1]

            # final sanity: if wallet_obj looks valid return what we have
            if hasattr(wallet_obj, "address"):
                return private_key, public_key, wallet_obj

    # if we reach here nothing worked
    raise RuntimeError("Unable to construct wallet from mnemonic with installed tonsdk. Last error: %s" % (last_exc,))


# --------------------- TONWallet class ---------------------
class TONWallet:
    def __init__(self):
        self.client = None
        self.wallet = None  # pytoniq WalletV4R2 instance used for transfers
        self.tonsdk_wallet = None  # optional tonsdk wallet object
        self.derived_address = None

        self.last_balance_check = datetime.min
        self.balance_cache = 0.0
        self.last_tx_check = datetime.min
        self.pending_withdrawals = {}
        self.initialized = False
        self.connection_retries = 0
        self.MAX_RETRIES = 3

        # network decision comes from config first, then env
        self.network = getattr(config, "TON_NETWORK", os.getenv("TON_NETWORK", "mainnet")).lower()
        self.is_testnet = self.network == "testnet"

        # load secrets: prefer TON_PRIVATE_KEY (base64), otherwise TON_MNEMONIC
        self.ton_private_key_b64 = getattr(config, "TON_PRIVATE_KEY", None) or os.getenv("TON_PRIVATE_KEY")
        self.ton_mnemonic = getattr(config, "TON_MNEMONIC", None) or os.getenv("TON_MNEMONIC")

    async def initialize(self):
        """Initialize TON wallet connection and ensure a usable hot wallet is available.
        The method will:
          - connect LiteClient to correct network
          - derive keys from TON_PRIVATE_KEY or TON_MNEMONIC
          - create a pytoniq WalletV4R2 for signing/transfers
        """
        try:
            # Select correct lite servers
            if self.is_testnet:
                self.client = LiteClient.from_testnet_config(ls_i=0, trust_level=2, timeout=60)
            else:
                self.client = LiteClient.from_mainnet_config(ls_i=0, trust_level=2, timeout=60)

            # Retry connection with exponential backoff
            while self.connection_retries < self.MAX_RETRIES:
                try:
                    await self.client.connect()
                    break
                except (asyncio.TimeoutError, ConnectionError) as e:
                    self.connection_retries += 1
                    wait_time = 2 ** self.connection_retries
                    logger.warning(
                        f"TON connection failed (attempt {self.connection_retries}/{self.MAX_RETRIES}): {e}. Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)

            if self.connection_retries >= self.MAX_RETRIES:
                raise ConnectionError("Failed to connect to TON network after multiple attempts")

            # CASE A: TON_PRIVATE_KEY provided (base64)
            if self.ton_private_key_b64:
                try:
                    private_key = base64.b64decode(self.ton_private_key_b64)
                    # create a pytoniq WalletV4R2 from private key
                    self.wallet = WalletV4R2(provider=self.client, private_key=private_key)
                    # derive user-friendly address
                    self.derived_address = self.wallet.address.to_str(test_only=self.is_testnet)
                    logger.info(f"TON Hot Wallet ({self.network}): {self._mask_address(self.derived_address)}")
                    self.initialized = True
                    return True
                except Exception as e:
                    logger.exception("Failed to use TON_PRIVATE_KEY; will try mnemonic if available.")

            # CASE B: Use mnemonic (preferred path when no raw key provided)
            if not self.ton_mnemonic:
                raise ValueError("No TON_PRIVATE_KEY or TON_MNEMONIC provided; cannot initialize hot wallet")

            # Ensure mnemonic is list of words
            if isinstance(self.ton_mnemonic, str):
                mnemonic_list = self.ton_mnemonic.strip().split()
            else:
                mnemonic_list = list(self.ton_mnemonic)

            # Attempt to build wallet via tonsdk helpers
            priv_key_bytes, pub_key_bytes, wallet_obj = _build_wallet_from_mnemonic(mnemonic_list)

            # If we extracted a private key, create pytoniq wallet for signing
            if priv_key_bytes:
                # Some pytoniq/WalletV4R2 constructors require an `address` positional arg (Contract base class).
                # Build a user-friendly derived address from the tonsdk wallet_obj (if available) and pass it in.
                addr_candidate = None
                try:
                    if wallet_obj is not None and hasattr(wallet_obj, "address"):
                        try:
                            addr_candidate = wallet_obj.address.to_string(True, True, self.is_testnet)
                        except Exception:
                            try:
                                addr_candidate = wallet_obj.address.to_str(test_only=self.is_testnet)
                            except Exception:
                                addr_candidate = None
                except Exception:
                    addr_candidate = None

                # pytoniq often expects a 64-byte private key (seed||pub). If we only got 32-byte seed, try concatenating pubkey too.
                candidate_keys = [priv_key_bytes]
                if isinstance(priv_key_bytes, (bytes, bytearray)) and isinstance(pub_key_bytes, (bytes, bytearray)) and len(priv_key_bytes) == 32:
                    candidate_keys.append(priv_key_bytes + pub_key_bytes)

                created = False
                last_exc = None
                for key in candidate_keys:
                    try:
                        if addr_candidate:
                            self.wallet = WalletV4R2(provider=self.client, private_key=key, address=Address(addr_candidate))
                        else:
                            # try without address (some pytoniq builds accept keyword 'address' later)
                            self.wallet = WalletV4R2(provider=self.client, private_key=key)

                        # if we reach here, wallet created successfully
                        try:
                            # derive user-friendly address from the created wallet
                            self.derived_address = self.wallet.address.to_str(test_only=self.is_testnet)
                        except Exception:
                            # fall back to addr_candidate if wallet doesn't expose to_str
                            self.derived_address = addr_candidate

                        logger.info(f"TON Hot Wallet ({self.network}): {self._mask_address(self.derived_address)}")
                        self.initialized = True
                        created = True
                        break
                    except Exception as e:
                        last_exc = e
                        # try next candidate key
                        continue

                if not created:
                    logger.exception("Failed to create WalletV4R2 from derived private key; tried possible key formats. Last error: %s", last_exc)

            # If we reach here, we have a wallet_obj but no usable private key for pytoniq
            # store tonsdk wallet for potential use (some tonsdk wallet objects support signing)
            self.tonsdk_wallet = wallet_obj
            try:
                # try to derive address from wallet_obj
                if hasattr(wallet_obj, "address"):
                    # different tonsdk versions have different address string methods
                    try:
                        self.derived_address = wallet_obj.address.to_string(True, True, self.is_testnet)
                    except Exception:
                        try:
                            self.derived_address = wallet_obj.address.to_str(test_only=self.is_testnet)
                        except Exception:
                            self.derived_address = str(wallet_obj.address)
                logger.info(f"TON Hot Wallet ({self.network}) (from tonsdk object): {self._mask_address(self.derived_address)}")
                # We can't guarantee signing capability — warn but allow read-only flows
                logger.warning("No raw private key available for pytoniq transfers; transfer attempts will fail unless tonsdk wallet supports signing in this env.")
                self.initialized = True
                return True
            except Exception:
                raise RuntimeError("Derived wallet object is unusable; provide TON_PRIVATE_KEY or install a compatible tonsdk that exposes private keys.")

        except Exception as e:
            logger.exception("TON wallet initialization failed")
            self.initialized = False
            return False

    async def get_balance(self, force_update=False) -> float:
        """Get current wallet balance in TON."""
        try:
            if not force_update and (datetime.now() - self.last_balance_check < timedelta(minutes=5)):
                return self.balance_cache

            if not self.initialized:
                await self.initialize()

            if self.wallet:
                balance = await self.wallet.get_balance()
            else:
                # fallback: query balance via lite client using derived address
                if not self.derived_address:
                    raise RuntimeError("No derived wallet address available to query balance")
                # pytoniq LiteClient provides get_account_state via request; we'll use client.request
                # Use a safe approach: use Address and ask for account state
                ac = await self.client.get_account(Address(self.derived_address))
                # ac may be dict-like with 'balance' in nanotons
                balance = ac.get('balance', 0) if isinstance(ac, dict) else 0

            ton_balance = balance / 1e9  # nanoton -> TON

            self.balance_cache = ton_balance
            self.last_balance_check = datetime.now()

            min_hot_balance = getattr(config, 'MIN_HOT_BALANCE', 0)
            if ton_balance < float(min_hot_balance):
                self.send_alert(f"🔥 TON HOT WALLET LOW BALANCE: {ton_balance:.6f} TON")

            return ton_balance
        except Exception as e:
            logger.exception(f"Failed to get TON balance: {e}")
            return 0.0

    async def send_transaction(self, destination: str, amount: float, memo: str = "") -> dict:
        """Send TON transaction to external address."""
        try:
            if not self.initialized:
                await self.initialize()

            if not self.wallet:
                raise RuntimeError("No signing-capable wallet available (no private key). Cannot send transaction.")

            # Convert TON -> nanotons (int)
            amount_nano = int(amount * 1e9)

            # Build body cell
            body = begin_cell()
            if memo:
                body.store_uint(0, 32)  # op code for comment
                body.store_string(memo)
            body = body.end_cell()

            # Execute transfer
            result = await self.wallet.transfer(
                destination=Address(destination),
                amount=amount_nano,
                body=body,
                timeout=120
            )

            logger.info(f"TON transaction sent: {amount:.6f} TON to {self._mask_address(destination)}")
            return {
                'status': 'success',
                'tx_hash': result.get('hash') if isinstance(result, dict) else None,
                'amount': amount,
                'destination': destination
            }
        except Exception as e:
            logger.exception(f"TON transaction failed: {e}")
            return {'status': 'error', 'error': str(e)}

    async def process_withdrawal(self, user_id: int, amount: float, address: str) -> dict:
        """Process TON withdrawal with security checks."""
        try:
            if self.get_user_daily_withdrawal(user_id) + amount > getattr(config, 'USER_DAILY_WITHDRAWAL_LIMIT', 100):
                return {'status': 'error', 'error': f"Daily withdrawal limit exceeded: {config.USER_DAILY_WITHDRAWAL_LIMIT} TON"}

            if self.get_system_daily_withdrawal() + amount > getattr(config, 'DAILY_WITHDRAWAL_LIMIT', 1000):
                return {'status': 'error', 'error': "System daily withdrawal limit reached"}

            result = await self.send_transaction(address, amount, f"Withdrawal for user {user_id}")

            if result['status'] == 'success':
                self.update_withdrawal_limits(user_id, amount)
                logger.info(f"Withdrawal processed: {amount:.6f} TON to {self._mask_address(address)}")
            else:
                logger.error(f"Withdrawal failed for user {user_id}: {result.get('error')}")

            return result
        except Exception as e:
            logger.exception(f"Withdrawal processing failed: {e}")
            return {'status': 'error', 'error': str(e)}

    def get_user_daily_withdrawal(self, user_id: int) -> float:
        return 0.0  # TODO: implement DB logic

    def get_system_daily_withdrawal(self) -> float:
        return 0.0  # TODO: implement DB logic

    def update_withdrawal_limits(self, user_id: int, amount: float):
        pass  # TODO: implement DB logic

    def send_alert(self, message: str):
        if getattr(config, 'ALERT_WEBHOOK', None):
            try:
                requests.post(config.ALERT_WEBHOOK, json={'text': message})
            except Exception as e:
                logger.error(f"Failed to send alert: {e}")
        logger.warning(message)

    async def close(self):
        if self.client:
            try:
                await self.client.close()
                logger.info("TON client connection closed")
            except Exception as e:
                logger.error(f"Error closing TON client: {e}")

    def _mask_address(self, addr: str) -> str:
        try:
            if not addr:
                return "<no-address>"
            return addr[:6] + "..." + addr[-6:]
        except Exception:
            return "<address>"

# Global TON wallet instance
ton_wallet = TONWallet()

async def initialize_ton_wallet():
    return await ton_wallet.initialize()

async def close_ton_wallet():
    return await ton_wallet.close()


def is_valid_ton_address(address: str) -> bool:
    try:
        Address(address)
        return True
    except Exception:
        return False


async def create_staking_contract(user_id: str, amount: float) -> str:
    logger.info(f"Creating staking contract for user {user_id} with {amount} TON")
    return f"EQ_STAKING_{user_id}_{int(time.time())}"


async def execute_swap(user_id: str, from_token: str, to_token: str, amount: float) -> str:
    logger.info(f"Executing swap for user {user_id}: {amount} {from_token} to {to_token}")
    return f"tx_{user_id}_{int(time.time())}"


async def process_ton_withdrawal(user_id: int, amount: float, address: str):
    return await ton_wallet.process_withdrawal(user_id, amount, address)
