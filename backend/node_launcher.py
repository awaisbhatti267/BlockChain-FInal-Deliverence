# Node_Launcher.py
import subprocess, time, sys, os, requests, threading
from pathlib import Path

PY = sys.executable

BASE_DIR = Path(__file__).resolve().parent
APP_PATH = BASE_DIR / "app.py"
LOG_DIR = BASE_DIR / "node_logs"
LOG_DIR.mkdir(exist_ok=True)

def start_node(port):
    env = os.environ.copy()
    env["PORT"] = str(port)
    stdout_path = LOG_DIR / f"node_{port}.out.log"
    stderr_path = LOG_DIR / f"node_{port}.err.log"
    stdout_f = open(stdout_path, "a", buffering=1, encoding="utf-8", errors="replace")
    stderr_f = open(stderr_path, "a", buffering=1, encoding="utf-8", errors="replace")
    p = subprocess.Popen([PY, str(APP_PATH)], env=env, cwd=str(BASE_DIR), stdout=stdout_f, stderr=stderr_f)
    return p, stdout_f, stderr_f, stdout_path, stderr_path

def wait_until_up(port, timeout=60):
    url = f"http://127.0.0.1:{port}/logs"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            time.sleep(0.5)
    return False

def add_peer(target_port, peer_url, retries=3, backoff=1.0):
    url = f"http://127.0.0.1:{target_port}/add_peer"
    for attempt in range(1, retries + 1):
        try:
            r = requests.post(url, json={"peer": peer_url}, timeout=3)
            if r.status_code == 200:
                print(f"[launcher] Added {peer_url} → {url}")
                return True
            else:
                print(f"[launcher] Unexpected response adding peer: {r.status_code} {r.text}")
        except Exception as e:
            print(f"[launcher] Retry {attempt}: could not add peer {peer_url} → {url}: {e}")
        time.sleep(backoff * attempt)
    return False

def tail_log_once(path, lines=20):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.read().splitlines()
            tail = all_lines[-lines:]
            return "\n".join(tail)
    except Exception:
        return ""

def monitor_processes(procs_info):
    while True:
        for port, info in list(procs_info.items()):
            p = info["proc"]
            if p.poll() is not None:
                code = p.returncode
                print(f"\n[launcher][ERROR] Node on port {port} exited with code {code}")
                print("---- last stdout ----")
                print(tail_log_once(info["stdout_path"], lines=60))
                print("---- last stderr ----")
                print(tail_log_once(info["stderr_path"], lines=60))
                procs_info.pop(port, None)
        time.sleep(1)

if __name__ == "__main__":
    ports = [5001, 5002, 5003, 5004, 5005]
    print("[launcher] Launching nodes:", ports)

    procs_info = {}
    for p in ports:
        proc, so_f, se_f, so_path, se_path = start_node(p)
        procs_info[p] = {"proc": proc, "stdout_f": so_f, "stderr_f": se_f, "stdout_path": so_path, "stderr_path": se_path}
        print(f"[launcher] Started node pid={proc.pid} on port {p} (logs: {so_path}, {se_path})")

    monitor_thread = threading.Thread(target=monitor_processes, args=(procs_info,), daemon=True)
    monitor_thread.start()

    for p in ports:
        ok = wait_until_up(p, timeout=40)
        if ok:
            print(f"[launcher] Node {p} is UP ✅")
        else:
            print(f"[launcher] ⚠️ Node {p} did not start within timeout (check {LOG_DIR}/node_{p}.err.log)")

    peers = [f"http://127.0.0.1:{p}" for p in ports]
    for target in ports:
        for peer in peers:
            if peer.endswith(f":{target}"):
                continue
            add_peer(target, peer)

    print("[launcher] ✅ Peers registered. Nodes running. To stop, press Ctrl-C.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[launcher] Stopping nodes...")
        for info in procs_info.values():
            try:
                info["proc"].terminate()
            except Exception:
                pass
            try:
                info["stdout_f"].close()
                info["stderr_f"].close()
            except Exception:
                pass
        time.sleep(0.5)
        sys.exit(0)
