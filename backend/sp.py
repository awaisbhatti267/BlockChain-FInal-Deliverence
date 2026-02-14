# Add CSV Logger Helper (backend)

# Add this function anywhere globally in your backend
# (preferably in the same file where transactions & mining occur):


import csv
import os

CSV_PATH = "data/logs.csv"

# Ensure CSV exists with header

if not os.path.exists(CSV_PATH):
    with open(CSV_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "txid", "sender", "receiver", "amount", "type"])


def append_log_to_csv(timestamp, txid, sender, receiver, amount, tx_type):
    """Append one structured log entry to CSV."""
    with open(CSV_PATH, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, txid, sender, receiver, amount, tx_type])


#-------------------------------------------------------------------------
# Modify backend to log every transaction

# Find where a transaction is added, mined, attacked, rejected, and add:

from time import time

append_log_to_csv(
    int(time()),
    tx.txid,
    tx.sender,
    tx.receiver,
    tx.amount,
    "attack-armed" if attacker_active else "normal"
)


# For example, in your mine_block() function (inside blockchain):

if tx_is_valid:
    append_log_to_csv(
        int(time()),
        tx.txid,
        tx.sender,
        tx.receiver,
        tx.amount,
        "normal"
    )

# For attack events:

append_log_to_csv(
    int(time()),
    attack_tx.txid,
    attack_tx.sender,
    attack_tx.receiver,
    attack_tx.amount,
    "attack-armed"
)


# New Backend API Endpoint — Serve CSV to Frontend

# Add this to your Flask backend:

@app.route("/api/logs_csv")
def get_logs_csv():
    return send_file("data/logs.csv", mimetype="text/csv")

from flask import send_file
#-------------------------------------------------------------------------

# FRONTEND — Update Dashboard to Use CSV
# Add this to your dashboard.html JS section:

async function loadCSVLogs() {
    const res = await fetch("http://127.0.0.1:5001/api/logs_csv");
    const csvText = await res.text();

    const rows = csvText.trim().split("\n").slice(1); // remove header

    const parsed = rows.map(r => {
        const [timestamp, txid, sender, receiver, amount, type] = r.split(",");
        return { timestamp, txid, sender, receiver, amount, type };
    });

    renderLogsTable(parsed);
    renderChart(parsed);
}


# Replace existing loadLogs() with:
    
setInterval(loadCSVLogs, 3000);
    loadCSVLogs();


# Updated Log Table Rendering

function renderLogsTable(logs) {
    const table = document.getElementById("logs-table");
    table.innerHTML = `
        <tr>
            <th>Timestamp</th>
            <th>TxID</th>
            <th>Sender</th>
            <th>Receiver</th>
            <th>Amount</th>
            <th>Type</th>
        </tr>
    `;

    logs.forEach(log => {
        table.innerHTML += `
            <tr>
                <td>${log.timestamp}</td>
                <td>${log.txid}</td>
                <td>${log.sender}</td>
                <td>${log.receiver}</td>
                <td>${log.amount}</td>
                <td>${log.type}</td>
            </tr>
        `;
    });
}
# -------------------------------------------------------------------------

# Updated Chart Rendering

function renderChart(logs) {
    const amounts = logs.map(l => Number(l.amount));
    const timestamps = logs.map(l => new Date(l.timestamp * 1000).toLocaleTimeString());

    if (window.txChart) window.txChart.destroy();

    window.txChart = new Chart(document.getElementById("chart"), {
        type: "line",
        data: {
            labels: timestamps,
            datasets: [{
                label: "Transaction Amounts",
                data: amounts,
                borderWidth: 2
            }]
        }
    });
}
