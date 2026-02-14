# attack_logger.py
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import csv
import os

from csv_logger import CSV_PATH

@dataclass
class AttackEvent:
    timestamp: float
    event: str
    details: dict

@dataclass
class AttackAnalytics:
    events: List[AttackEvent] = field(default_factory=list)
    time_series: List[dict] = field(default_factory=list)
    orphan_blocks: List[str] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=lambda: {
        "attacker_blocks": 0,
        "honest_blocks": 0,
        "reorgs": 0,
        "private_blocks_mined": 0,
        "private_blocks_published": 0
    })
    result: Optional[str] = None

    def log(self, event: str, **details):
        entry = AttackEvent(timestamp=time.time(), event=event, details=details)
        self.events.append(entry)

    def log_private_block(self, block_hash: str, height: int):
        self.stats["private_blocks_mined"] += 1
        self.log("private_block_mined", block_hash=block_hash, height=height)

    def log_publish(self, count: int):
        self.stats["private_blocks_published"] += count
        self.log("private_chain_published", blocks=count)

    def log_reorg(self, old_tip: str, new_tip: str, orphaned: List[str]):
        self.stats["reorgs"] += 1
        self.orphan_blocks.extend(orphaned)
        self.log("chain_reorg", old_tip=old_tip, new_tip=new_tip, orphaned_blocks=orphaned)

    def log_attacker_lead(self, honest_height: int, private_height: int):
        lead = private_height - honest_height
        self.time_series.append({
            "timestamp": time.time(),
            "honest_height": honest_height,
            "private_height": private_height,
            "lead": lead,
        })
        self.log("lead_update", lead=lead)

    def log_block(self, miner: str, block_hash: str):
        if miner == "attacker":
            self.stats["attacker_blocks"] += 1
        else:
            self.stats["honest_blocks"] += 1
        self.log("block_mined", miner=miner, block_hash=block_hash)

    def set_result(self, result: str):
        self.result = result
        self.log("attack_result", result=result)

    def export(self):
        return {
            "events": [
                {"time": e.timestamp, "event": e.event, "details": e.details} for e in self.events
            ],
            "stats": self.stats,
            "orphan_blocks": self.orphan_blocks,
            "timeline": self.time_series,
            "result": self.result
        }

class AttackLogger:
    def __init__(self, csv_path=CSV_PATH):
        self.csv_path = csv_path
        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["timestamp", "txid", "sender", "receiver", "amount", "type"])

    def log(self, txid, sender, receiver, amount, event_type):
        timestamp = int(time.time())
        with open(self.csv_path, "a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([timestamp, txid, sender, receiver, amount, event_type])
        return {"timestamp": timestamp, "txid": txid, "sender": sender, "receiver": receiver, "amount": amount, "type": event_type}

if not os.path.exists(CSV_PATH):
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    with open(CSV_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "txid", "sender", "receiver", "amount", "type"])
