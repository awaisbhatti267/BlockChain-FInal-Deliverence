# blockchain.py
import time, json, hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from csv_logger import append_log_to_csv

def sha256(x: str) -> str:
    return hashlib.sha256(x.encode()).hexdigest()

DIFFICULTY_PREFIX = "000"

@dataclass
class Tx:
    sender: str
    receiver: str
    amount: int
    nonce: int
    txid: str = ""

    def to_json(self):
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "amount": int(self.amount),
            "nonce": int(self.nonce),
            "txid": self.txid,
        }

    def compute_txid(self):
        self.txid = sha256(f"{self.sender}|{self.receiver}|{self.amount}|{self.nonce}")
        return self.txid

    @staticmethod
    def from_json(d: dict):
        return Tx(
            str(d.get("sender", "")),
            str(d.get("receiver", "")),
            int(d.get("amount", 0)),
            int(d.get("nonce", 0)),
            d.get("txid", "")
        )

@dataclass
class Block:
    index: int
    prev_hash: str
    timestamp: float
    nonce: int
    txs: List[Tx] = field(default_factory=list)

    def header(self):
        tx_str = json.dumps([t.to_json() for t in self.txs], sort_keys=True)
        return f"{self.index}|{self.prev_hash}|{self.timestamp}|{self.nonce}|{tx_str}"

    def hash(self):
        return sha256(self.header())

class Blockchain:

    def __init__(self, alloc: Dict[str, int]):
        self.genesis_balances = {a: int(v) for a, v in alloc.items()}
        self.balances = self.genesis_balances.copy()
        self.nonces = {a: 0 for a in alloc}
        self.mempool: Dict[str, Tx] = {}

        self.blocks: Dict[str, Block] = {}
        self.parents: Dict[str, Optional[str]] = {}
        self.children: Dict[str, List[str]] = {}
        self.block_height: Dict[str, int] = {}

        genesis = Block(0, "GENESIS", time.time(), 0, [])
        ghash = genesis.hash()

        self.blocks[ghash] = genesis
        self.parents[ghash] = None
        self.children[ghash] = []
        self.block_height[ghash] = 0

        self.genesis_hash = ghash
        self.best_tip = ghash

    def validate_tx(self, tx: Tx) -> bool:
        if tx.txid == "":
            tx.compute_txid()
        if tx.sender not in self.balances:
            return False
        if self.balances[tx.sender] < tx.amount:
            return False
        if self.nonces.get(tx.sender, 0) != tx.nonce:
            return False
        return True

    def add_tx(self, tx: Tx) -> bool:
        if self.validate_tx(tx):
            self.mempool[tx.txid] = tx
            append_log_to_csv(tx, "mempool-add")
            return True
        return False

    def verify_pow(self, block: Block) -> bool:
        return block.hash().startswith(DIFFICULTY_PREFIX)

    def path_to_genesis(self, tip_hash: str):
        path = []
        cur = tip_hash
        while cur is not None:
            path.append(cur)
            cur = self.parents[cur]
        return path

    def rebuild_state(self):
        self.balances = self.genesis_balances.copy()
        self.nonces = {a: 0 for a in self.nonces}
        chain_hashes = list(reversed(self.path_to_genesis(self.best_tip)))
        for h in chain_hashes:
            if h == self.genesis_hash:
                continue
            block = self.blocks[h]
            for tx in block.txs:
                if tx.sender == "COINBASE":
                    self.balances[tx.receiver] = self.balances.get(tx.receiver, 0) + tx.amount
                else:
                    if self.balances[tx.sender] >= tx.amount and self.nonces[tx.sender] == tx.nonce:
                        self.balances[tx.sender] -= tx.amount
                        self.balances[tx.receiver] = self.balances.get(tx.receiver, 0) + tx.amount
                        self.nonces[tx.sender] += 1

    def add_block(self, block: Block) -> bool:
        bh = block.hash()
        if block.prev_hash not in self.blocks:
            return False
        if not self.verify_pow(block):
            return False
        self.blocks[bh] = block
        self.parents[bh] = block.prev_hash
        self.children.setdefault(bh, [])
        self.children[block.prev_hash].append(bh)
        self.block_height[bh] = self.block_height[block.prev_hash] + 1
        for tx in block.txs:
            append_log_to_csv(tx, "block-accepted")
        if self.block_height[bh] > self.block_height[self.best_tip]:
            self.best_tip = bh
            self.rebuild_state()
        return True

    def mine_block(self, miner_addr: str, reward=50):
        coinbase = Tx("COINBASE", miner_addr, reward, 0)
        coinbase.compute_txid()
        txs = [coinbase] + list(self.mempool.values())
        parent = self.blocks[self.best_tip]
        block = Block(
            index=parent.index + 1,
            prev_hash=self.best_tip,
            timestamp=time.time(),
            nonce=0,
            txs=txs
        )
        while not block.hash().startswith(DIFFICULTY_PREFIX):
            block.nonce += 1
        self.add_block(block)
        self.mempool.clear()
        return block

    def find_tx_block(self, txid: str) -> Optional[str]:
        chain = reversed(self.path_to_genesis(self.best_tip))
        for bh in chain:
            if bh == self.genesis_hash:
                continue
            for tx in self.blocks[bh].txs:
                if tx.txid == txid:
                    return bh
        return None

    def confirmations(self, txid: str) -> int:
        bh = self.find_tx_block(txid)
        if bh is None:
            return 0
        return 1 + (self.block_height[self.best_tip] - self.block_height[bh])

    def is_tx_confirmed(self, txid: str, depth: int) -> bool:
        return self.confirmations(txid) >= depth

    def tx_removed_by_reorg(self, txid: str, depth: int) -> bool:
        bh = self.find_tx_block(txid)
        if bh is None:
            return True
        return self.confirmations(txid) < depth
