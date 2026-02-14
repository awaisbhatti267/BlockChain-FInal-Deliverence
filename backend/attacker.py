# attacker.py
import time
import random
from typing import Dict, Optional
from dataclasses import dataclass, field

from blockchain import Tx, Block, sha256, DIFFICULTY_PREFIX
from csv_logger import append_log_to_csv
from attack_logger import AttackAnalytics

@dataclass
class Attacker:
    blockchain: object
    attacker_address: str
    hash_power: float

    active: bool = False
    target_tx: Optional[Tx] = None
    double_spend_tx: Optional[Tx] = None

    attack_chain_tip: Optional[str] = None
    attack_blocks: Dict[str, Block] = field(default_factory=dict)
    attack_parents: Dict[str, Optional[str]] = field(default_factory=dict)
    attack_height: Dict[str, int] = field(default_factory=dict)

    analytics: AttackAnalytics = field(default_factory=AttackAnalytics)

    def start_attack(self, victim_tx: Tx, double_spend_tx: Tx):
        self.active = True
        self.target_tx = victim_tx
        self.double_spend_tx = double_spend_tx
        append_log_to_csv(double_spend_tx, "attack-armed")
        self.analytics.log("attack_armed", victim_txid=victim_tx.txid, double_txid=double_spend_tx.txid)
        tip = self.blockchain.best_tip
        self.attack_chain_tip = tip
        self.attack_blocks.clear()
        self.attack_parents.clear()
        self.attack_height = {tip: self.blockchain.block_height[tip]}
        print("[ATTACK] Secret-chain attack STARTED")

    def attacker_wins_next_block(self):
        return random.random() < self.hash_power

    def mine_private_block(self):
        parent_hash = self.attack_chain_tip
        parent_block = (
            self.blockchain.blocks[parent_hash]
            if parent_hash not in self.attack_blocks
            else self.attack_blocks[parent_hash]
        )

        txs = [self.double_spend_tx]

        coinbase = Tx("COINBASE", self.attacker_address, 50, 0)
        coinbase.compute_txid()
        txs.insert(0, coinbase)

        b = Block(
            index=parent_block.index + 1,
            prev_hash=parent_hash,
            timestamp=time.time(),
            nonce=0,
            txs=txs
        )

        while not b.hash().startswith(DIFFICULTY_PREFIX):
            b.nonce += 1

        bh = b.hash()

        self.attack_blocks[bh] = b
        self.attack_parents[bh] = parent_hash
        self.attack_height[bh] = self.attack_height[parent_hash] + 1
        self.attack_chain_tip = bh

        for tx in txs:
            append_log_to_csv(tx, "attack-private-mine")

        self.analytics.log_private_block(bh, b.index)
        self.analytics.log_block("attacker", bh)

        print(f"[ATTACK] Private block mined {bh[:12]}")

    def should_publish(self):
        honest = self.blockchain.block_height[self.blockchain.best_tip]
        private = self.attack_height[self.attack_chain_tip]
        return private > honest

    def build_private_path(self):
        path = []
        h = self.attack_chain_tip
        while h and h != self.blockchain.genesis_hash:
            if h in self.attack_blocks:
                path.append(h)
            h = self.attack_parents.get(h)
        return list(reversed(path))

    def publish_chain(self):
        print("[ATTACK] Publishing private chain...")
        path = self.build_private_path()
        for h in path:
            block = self.attack_blocks[h]
            for tx in block.txs:
                append_log_to_csv(tx, "attack-published")
            self.blockchain.add_block(block)
        self.analytics.log_publish(len(path))
        self.analytics.log("private_chain_published", count=len(path))

    def check_success(self, required_confirmations):
        if not self.active:
            return None

        victim_txid = self.target_tx.txid

        if self.blockchain.find_tx_block(victim_txid) is None:
            append_log_to_csv(self.target_tx, "attack-success")
            self.analytics.set_result("attack_success")
            self.active = False
            print("[ATTACK] SUCCESS")
            return "attack_success"

        conf = self.blockchain.confirmations(victim_txid)
        if conf >= required_confirmations:
            append_log_to_csv(self.target_tx, "attack-fail")
            self.analytics.set_result("attack_fail")
            self.active = False
            print("[ATTACK] FAIL")
            return "attack_fail"

        return None

    def tick(self, required_confirmations=6):
        if not self.active:
            return None

        result = self.check_success(required_confirmations)
        if result:
            return result

        if self.attacker_wins_next_block():
            self.mine_private_block()

            if self.should_publish():
                self.publish_chain()
                return self.check_success(required_confirmations)

        return None
