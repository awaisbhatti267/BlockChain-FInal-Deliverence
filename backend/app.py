# app.py (final — includes /get_params, /set_params, /attack_analytics, /attack_analytics_history aliases)
import threading
from flask import Flask, request, jsonify, send_file
import requests, time, json, os, random
from typing import List, Dict
from threading import Lock
from flask_cors import CORS

from attacker import Attacker
from attack_logger import AttackAnalytics
from blockchain import Blockchain, Tx, Block, sha256, DIFFICULTY_PREFIX
from csv_logger import CSV_PATH, append_log_to_csv

import sys
import io

# Force UTF-8 for stdout on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

app = Flask(__name__, static_folder="Front-End")
CORS(app)

# -----------------------------
# Globals / Config
# -----------------------------
INITIAL_ALLOC = {"alice": 100, "bob": 50, "attacker": 500, "merchant": 100, "miner": 0}
bc_lock = Lock()
bc = Blockchain(INITIAL_ALLOC)

# Create a single AttackAnalytics instance and pass it to the Attacker
attack_analytics = AttackAnalytics()
attacker = Attacker(blockchain=bc, attacker_address="attacker", hash_power=0.5, analytics=attack_analytics)

PEERS = set()
EVENT_LOGS: List[str] = []
PARAMS_FILE = "sim_params.json"
LOG_FILE = "logs.txt"
DEFAULT_NETWORK_DELAY_MS = 50

if not os.path.exists(LOG_FILE):
    open(LOG_FILE, "w", encoding="utf-8").close()

# Ensure data dir exists for CSV_LOG path
csv_dir = os.path.dirname(CSV_PATH) or "data"
if csv_dir and not os.path.exists(csv_dir):
    os.makedirs(csv_dir, exist_ok=True)

# -----------------------------
# Logging
# -----------------------------
def add_log(message: str):
    ts = int(time.time())
    entry = f"[{ts}] {message}"
    print(entry)
    EVENT_LOGS.append(entry)
    if len(EVENT_LOGS) > 2000:
        EVENT_LOGS.pop(0)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except:
        pass

# -----------------------------
# Helpers
# -----------------------------
def serialize_block(b: Block):
    return {
        "index": b.index,
        "prev_hash": b.prev_hash,
        "timestamp": b.timestamp,
        "nonce": b.nonce,
        "txs": [t.to_json() for t in b.txs],
        "hash": b.hash(),
    }

def _do_post(url: str, payload: dict, timeout=3):
    try:
        requests.post(url, json=payload, timeout=timeout)
        add_log(f"[BPOST] POST {url} OK")
    except Exception as e:
        add_log(f"[WARN] POST {url} failed: {e}")

def broadcast_to_peers(path: str, payload: dict, base_delay_ms=None):
    params = load_params()
    base = base_delay_ms if base_delay_ms is not None else int(
        params.get("NETWORK_DELAY_MS",
                   params.get("ATTACKER_NETWORK_DELAY_MS",
                              DEFAULT_NETWORK_DELAY_MS))
    )
    for p in list(PEERS):
        jitter = (random.random() * 0.4 - 0.2)
        delay_ms = max(0, int(base * (1.0 + jitter)))
        url = p.rstrip("/") + path
        add_log(f"[BCAST] schedule {url} in {delay_ms} ms")
        threading.Timer(delay_ms / 1000.0, _do_post, args=(url, payload)).start()

def save_params(params: dict):
    try:
        with open(PARAMS_FILE, "w", encoding="utf-8") as f:
            json.dump(params, f, indent=2)
        return True
    except Exception as e:
        add_log(f"[WARN] save_params failed: {e}")
        return False

def load_params():
    if os.path.exists(PARAMS_FILE):
        try:
            with open(PARAMS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            add_log(f"[WARN] load_params failed: {e}")
            return {}
    return {}

# Ensure sim_params.json exists with defaults if missing
if not os.path.exists(PARAMS_FILE):
    default_params = {
        "NETWORK_DELAY_MS": 50,
        "ATTACKER_HASH_POWER_SHARE": 0.5,
        "CONFIRMATIONS": 6,
        "attack_armed": False
    }
    save_params(default_params)

# -----------------------------
# Peer routes
# -----------------------------
@app.route("/logs", methods=["GET"])
def get_logs():
    return jsonify(EVENT_LOGS[-400:])

@app.route("/add_peer", methods=["POST"])
def add_peer():
    peer = request.json.get("peer")
    if peer and peer not in PEERS:
        PEERS.add(peer)
        add_log(f"Peer added: {peer}")
    return jsonify({"peers": list(PEERS)})

@app.route("/peers", methods=["GET"])
def peers():
    return jsonify({"peers": list(PEERS)})

# -----------------------------
# Core API
# -----------------------------
@app.route("/api/chain", methods=["GET"])
def api_chain():
    with bc_lock:
        path = list(reversed(bc.path_to_genesis(bc.best_tip)))
        chain_blocks = []
        for h in path:
            block = bc.blocks.get(h)
            if block is None:
                continue
            chain_blocks.append(serialize_block(block))
    return jsonify(chain_blocks)

# alias without /api
@app.route("/api/chain", methods=["GET"])
def alias_api_chain():
    return api_chain()

@app.route("/api/balance/<addr>", methods=["GET"])
def api_balance(addr):
    with bc_lock:
        return jsonify({
            "balance": bc.balances.get(addr, 0),
            "nonce": bc.nonces.get(addr, 0)
        })

@app.route("/api/mempool", methods=["GET"])
def api_mempool():
    with bc_lock:
        txs = [t.to_json() for t in bc.mempool.values()]
    return jsonify(txs)

# -----------------------------
# TX + Attack Logic
# -----------------------------
@app.route("/api/tx", methods=["POST"])
def api_tx():
    data = request.json
    tx = Tx.from_json(data)
    tx.compute_txid()
    params = load_params()

    with bc_lock:
        mined_block = None

        if params.get("attack_armed", False):
            params["attack_armed"] = False
            params["attack_triggered"] = True
            params["target_txid"] = tx.txid
            save_params(params)

            add_log(f"[ATTACK-ARMED] Attack attempt on tx {tx.txid}")

            attacker_nonce = bc.nonces.get("attacker", 0)
            attacker_tx = Tx("attacker", "merchant", tx.amount, attacker_nonce)
            attacker_tx.compute_txid()
            bc.add_tx(attacker_tx)

            share = float(params.get("ATTACKER_HASH_POWER_SHARE", 0.5))
            r = random.random()

            if r < share:
                mined_block = bc.mine_block("attacker")
                add_log(f"[ATTACK-SUCCESS] Attacker mined block {mined_block.index}")
                broadcast_to_peers("/block_gossip", serialize_block(mined_block))
                return jsonify({
                    "accepted": True,
                    "attacked": True,
                    "result": "attacker_mined",
                    "mined_block": serialize_block(mined_block)
                })
            else:
                if bc.add_tx(tx):
                    mined_block = bc.mine_block("miner")
                    add_log(f"[ATTACK-FAIL] Transaction {tx.txid} accepted")
                    broadcast_to_peers("/block_gossip", serialize_block(mined_block))
                    return jsonify({
                        "accepted": True,
                        "attacked": True,
                        "result": "attacker_lost",
                        "mined_block": serialize_block(mined_block)
                    })
                else:
                    add_log(f"[ATTACK-FAIL] tx rejected")
                    return jsonify({
                        "accepted": False,
                        "attacked": True,
                        "result": "attacker_lost_tx_rejected"
                    })

        ok = bc.add_tx(tx)
        if ok:
            add_log(f"Transaction {tx.txid} accepted")
            mined_block = bc.mine_block("miner")
            add_log(f"Block {mined_block.index} mined")
            broadcast_to_peers("/block_gossip", serialize_block(mined_block))
        else:
            add_log(f"Transaction {tx.txid} rejected")

    return jsonify({
        "accepted": ok,
        "attacked": False,
        "txid": tx.txid,
        "mined_block": serialize_block(mined_block) if mined_block else None
    })

# alias for old frontend (no /api prefix)
@app.route("/tx", methods=["POST"])
def alias_tx():
    return api_tx()

@app.route("/api/logs_csv")
def get_logs_csv():
    if os.path.exists(CSV_PATH):
        return send_file(CSV_PATH, mimetype="text/csv", as_attachment=True, download_name=os.path.basename(CSV_PATH))
    return jsonify({"error": "csv not found"}), 404

# -----------------------------
# Attack Control
# -----------------------------
@app.route("/api/start_attack", methods=["POST"])
def start_attack():
    data = request.json
    victim_tx = Tx.from_json(data["victim_tx"])
    double_spend_tx = Tx.from_json(data["double_spend_tx"])
    attacker.start_attack(victim_tx, double_spend_tx)
    return jsonify({"status": "attack_started"})

@app.route("/api/attack_analytics", methods=["GET"])
def attack_analytics_view():
    return jsonify(attack_analytics.export())

# alias endpoint expected by frontend (no /api)
@app.route("/attack_analytics", methods=["GET"])
def alias_attack_analytics():
    return attack_analytics_view()

# provide a simple history endpoint for the chart
@app.route("/attack_analytics_history", methods=["GET"])
def attack_analytics_history():
    # produce a small time-series snapshot using analytics.time_series + stats
    exported = attack_analytics.export()
    time_series = exported.get("timeline", [])
    # if empty produce a synthetic item
    if not time_series:
        stats = exported.get("stats", {})
        entry = {
            "timestamp": int(time.time() * 1000),
            "successful_attacks": stats.get("attacker_blocks", 0),
            "failed_attacks": stats.get("reorgs", 0)
        }
        return jsonify([entry])
    # transform to expected format
    hist = []
    for t in time_series:
        hist.append({
            "timestamp": t.get("timestamp", int(time.time()*1000)),
            "successful_attacks": exported["stats"].get("attacker_blocks", 0),
            "failed_attacks": exported["stats"].get("reorgs", 0)
        })
    return jsonify(hist)

@app.route("/run_attack", methods=["POST"])
def run_attack():
    data = request.json or {}
    params = load_params()
    params["attack_armed"] = True
    params["trigger_info"] = data
    save_params(params)
    add_log(f"Run-attack armed: {data}")
    return jsonify({"status": "attack_armed", "params": params})

# -----------------------------
# Dashboard / params endpoints (used by dashboard to update sim_params.json)
# -----------------------------
@app.route("/api/set_params", methods=["POST"])
def api_set_params():
    data = request.json or {}
    params = load_params()
    params.update(data)
    if save_params(params):
        add_log(f"[PARAMS] Updated params via API: {data}")
        return jsonify({"status": "ok", "params": params})
    else:
        return jsonify({"status": "error", "message": "could not save params"}), 500

# alias without /api
@app.route("/set_params", methods=["POST"])
def alias_set_params():
    return api_set_params()

@app.route("/api/get_params", methods=["GET"])
def api_get_params():
    return jsonify({"params": load_params()})

@app.route("/get_params", methods=["GET"])
def alias_get_params():
    return api_get_params()


# -----------------------------
# Run Flask App
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Flask node on port {port}")

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
    )
