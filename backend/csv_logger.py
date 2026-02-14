# csv_logger.py
import csv
import os
import time
import re

# Per-node CSV file (uses PORT env var; default 5000)
PORT = os.environ.get("PORT", "5000")
DATA_DIR = "data"
CSV_PATH = os.path.join(DATA_DIR, f"logs_{PORT}.csv")

# Ensure data dir exists
os.makedirs(DATA_DIR, exist_ok=True)

# CSV header
HEADER = ["timestamp", "txid", "sender", "receiver", "amount", "type"]

# Create CSV with header if missing
if not os.path.exists(CSV_PATH):
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)


# regex to parse stringified Tx(...) produced by repr/str
_TX_RE = re.compile(
    r"Tx\(\s*sender=(?:'(?P<sender1>[^']*)'|\"(?P<sender2>[^\"]*)\"|(?P<sender3>[^,]*)),\s*"
    r"receiver=(?:'(?P<receiver1>[^']*)'|\"(?P<receiver2>[^\"]*)\"|(?P<receiver3>[^,]*)),\s*"
    r"amount=(?P<amount>\d+),.*?txid=(?:'(?P<txid1>[^']*)'|\"(?P<txid2>[^\"]*)\"|(?P<txid3>[^)\s]*))"
)


def _parse_tx_like(tx):
    """
    Return (txid, sender, receiver, amount) extracted from different tx forms:
     - object with attributes (tx.txid, tx.sender, tx.receiver, tx.amount)
     - dict-like with keys 'txid','sender','receiver','amount'
     - string like "Tx(sender='alice', receiver='bob', amount=10, nonce=0, txid='...')"
    Fallback: return empty strings / 0 where not available.
    """
    # object with attributes
    try:
        if hasattr(tx, "to_json") and callable(getattr(tx, "to_json")):
            j = tx.to_json()
            return (j.get("txid", ""), j.get("sender", ""), j.get("receiver", ""), int(j.get("amount", 0)))
        # dataclass-like or plain object
        if all(hasattr(tx, attr) for attr in ("txid", "sender", "receiver", "amount")):
            return (getattr(tx, "txid") or "", getattr(tx, "sender") or "", getattr(tx, "receiver") or "", int(getattr(tx, "amount") or 0))
    except Exception:
        pass

    # dict-like
    try:
        if isinstance(tx, dict):
            return (tx.get("txid", ""), tx.get("sender", ""), tx.get("receiver", ""), int(tx.get("amount", 0)))
    except Exception:
        pass

    # str like "Tx(sender='alice', receiver='bob', amount=10, nonce=0, txid='...')"
    try:
        if isinstance(tx, str):
            m = _TX_RE.search(tx)
            if m:
                txid = m.group("txid1") or m.group("txid2") or m.group("txid3") or ""
                sender = m.group("sender1") or m.group("sender2") or m.group("sender3") or ""
                receiver = m.group("receiver1") or m.group("receiver2") or m.group("receiver3") or ""
                amount = int(m.group("amount") or 0)
                return (txid, sender, receiver, amount)
    except Exception:
        pass

    # fallback: try to stringify (use as txid) and empty sender/receiver/amount=0
    try:
        return (str(tx), "", "", 0)
    except Exception:
        return ("", "", "", 0)


def append_log_to_csv(*args):
    """
    Append a structured log row to the per-node CSV file.

    Supported call patterns:
      1) append_log_to_csv(tx, "type")  -- tx can be object/dict/string
      2) append_log_to_csv(timestamp, txid, sender, receiver, amount, type)

    The function normalizes values and writes a clean CSV row:
      timestamp (int epoch seconds),
      txid (string),
      sender (string),
      receiver (string),
      amount (int),
      type (string)
    """
    row = None

    # Case 1: append_log_to_csv(tx, type)
    if len(args) == 2:
        tx, ev_type = args
        ts = int(time.time())
        txid, sender, receiver, amount = _parse_tx_like(tx)
        try:
            amount = int(amount)
        except Exception:
            amount = 0
        row = [ts, txid, sender, receiver, amount, ev_type]

    # Case 2: full row provided (timestamp, txid, sender, receiver, amount, type)
    elif len(args) == 6:
        try:
            ts = int(args[0]) if args[0] else int(time.time())
        except Exception:
            ts = int(time.time())
        txid = args[1] or ""
        sender = args[2] or ""
        receiver = args[3] or ""
        try:
            amount = int(args[4])
        except Exception:
            amount = 0
        ev_type = args[5] or ""
        row = [ts, txid, sender, receiver, amount, ev_type]

    else:
        # Try to be tolerant: if a single arg is a list/tuple with 6 items
        if len(args) == 1 and (isinstance(args[0], (list, tuple)) and len(args[0]) == 6):
            r = args[0]
            try:
                ts = int(r[0]) if r[0] else int(time.time())
            except Exception:
                ts = int(time.time())
            row = [ts, r[1] or "", r[2] or "", r[3] or "", int(r[4]) if r[4] else 0, r[5] or ""]
        else:
            # unsupported signature
            raise ValueError("append_log_to_csv: unsupported arguments. Use (tx, type) or (timestamp,txid,sender,receiver,amount,type)")

    # Write row (append)
    try:
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(row)
    except Exception as e:
        # Last resort: try to create the file and write header then row
        try:
            with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(HEADER)
                writer.writerow(row)
        except Exception:
            # if even that fails, raise to surface the problem
            raise e

    # return row for convenience (useful in tests)
    return {
        "timestamp": row[0],
        "txid": row[1],
        "sender": row[2],
        "receiver": row[3],
        "amount": row[4],
        "type": row[5]
    }
