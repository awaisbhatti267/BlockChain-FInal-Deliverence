// script.js



// =====================
// CONFIG
// =====================
const NODE_BASE = "http://127.0.0.1:5001"; // Backend port

// =====================
// HELPERS
// =====================
async function nodeGet(path) {
  const res = await fetch(`${NODE_BASE}${path}`);
  return res.json();
}

async function nodePost(path, body) {
  const res = await fetch(`${NODE_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {})
  });
  return res.json();
}

// =====================
// DASHBOARD REFRESH
// =====================
async function refreshDashboard() {
  const boxes = document.querySelectorAll(".boxes");
  if (!boxes || boxes.length === 0) return; // Not on dashboard

  try {
    // ✅ FIX: Correct API endpoints
    const chain = await nodeGet("/api/chain");
    const last = chain[chain.length - 1];

    boxes[0].innerHTML = `
      <div style="padding:8px;color:#FFD700;font-family:Arial;font-size:14px;">
        <b>Chain Height:</b> ${chain.length - 1}<br/>
        <b>Last Block Hash:</b> ${String(last.hash).slice(0, 10)}...
      </div>`;

    const miner = await nodeGet("/api/balance/miner");
    boxes[1].innerHTML = `
      <div style="padding:8px;color:#FFD700;font-family:Arial;font-size:14px;">
        <b>Miner Balance:</b> ${miner.balance}
      </div>`;

    const alice = await nodeGet("/api/balance/alice");
    const bob = await nodeGet("/api/balance/bob");
    boxes[2].innerHTML = `
      <div style="padding:8px;color:#FFD700;font-family:Arial;font-size:14px;">
        <b>Alice:</b> ${alice.balance} (nonce ${alice.nonce})<br/>
        <b>Bob:</b> ${bob.balance} (nonce ${bob.nonce})
      </div>`;
  } catch (err) {
    console.error("Error loading dashboard:", err);
  }
}

setInterval(refreshDashboard, 3000);
refreshDashboard();

// =====================
// DASHBOARD BUTTONS
// =====================
const mineBtn = document.getElementById("minebtn");
if (mineBtn) {
  mineBtn.addEventListener("click", async () => {
    try {
      const r = await nodePost("/api/mine", { miner: "miner" });
      alert("⛏️ Mined Block #" + r.block.index);
      refreshDashboard();
    } catch (err) {
      alert("Mining failed (is backend running?)");
    }
  });
}

// =====================
// TRANSACTION PAGE SUPPORT
// =====================
const txForm = document.getElementById("txForm");
if (txForm) {
  txForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = new FormData(txForm);
    const payload = {
      sender: form.get("sender"),
      receiver: form.get("receiver"),
      amount: Number(form.get("amount")),
      nonce: Number(form.get("nonce"))
    };

    try {
      const r = await nodePost("/api/tx", payload);

      if (r.accepted) {
        // ✅ Transaction accepted popup
        const blockIndex = r.mined_block ? r.mined_block.index : "N/A";
        const txid = r.txid.substring(0, 10);

        // Create popup dynamically
        const popup = document.createElement("div");
        popup.style.position = "fixed";
        popup.style.top = "20px";
        popup.style.right = "20px";
        popup.style.background = "#1a1a1a";
        popup.style.color = "#00ff00";
        popup.style.padding = "15px";
        popup.style.borderRadius = "10px";
        popup.style.fontFamily = "Arial";
        popup.style.boxShadow = "0 0 10px rgba(0,255,0,0.7)";
        popup.innerHTML = `✅ Transaction accepted<br>🆔 TXID: ${txid}...<br>📦 Included in Block #${blockIndex}`;
        document.body.appendChild(popup);

        // Auto-remove popup after 4 seconds
        setTimeout(() => popup.remove(), 4000);

        // Reset form
        txForm.reset();

        // Refresh dashboard + mempool right away
        refreshDashboard();
        refreshMempool();

      } else {
        alert("❌ Transaction rejected (Check balance/nonce).");
      }
    } catch (err) {
      console.error(err);
      alert("⚠️ Error sending transaction. Backend may not be running.");
    }
  });
}


// =====================
// EXIT BUTTON
// =====================
const exitBtn = document.getElementById("exitbtn");
if (exitBtn) {
  exitBtn.addEventListener("click", () => {
    window.location.href = "index.html";
  });
}

// =====================
// CREATE TRANSACTION BUTTON
// =====================
const createbtn = document.getElementById("createbtn");
if (createbtn) {
  createbtn.addEventListener("click", () => {
    window.location.href = "transaction.html";
  });
}

// =====================
// RUN ATTACK BUTTON
// =====================
const runattackbtn = document.getElementById("runattackbtn");
if (runattackbtn) {
  runattackbtn.addEventListener("click", async () => {
    try {
      const res = await fetch(`${NODE_BASE}/run_attack`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ requested_by: "dashboard", ts: Date.now() })
      });
      const result = await res.json();
      alert("🚨 Attack Armed! Next transaction will be attacked.");
      console.log("Run attack response:", result);
    } catch (err) {
      console.error("Error triggering attack:", err);
      alert("⚠️ Could not trigger attack (backend offline?).");
    }
  });
}
async function refreshMempool() {
  const mempoolTable = document.querySelector("#mempoolTable tbody");
  if (!mempoolTable) return; // only run if table exists on page

  try {
    const res = await fetch(`${NODE_BASE}/api/mempool`);
    const mempool = await res.json();

    mempoolTable.innerHTML = "";

    if (mempool.length === 0) {
      mempoolTable.innerHTML = `<tr><td colspan="4" style="color:#FFD700;">No pending transactions</td></tr>`;
      return;
    }

    mempool.forEach(tx => {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td style="color:#FFD700;">${tx.txid.substring(0, 10)}...</td>
        <td style="color:#FFD700;">${tx.sender}</td>
        <td style="color:#FFD700;">${tx.receiver}</td>
        <td style="color:#FFD700;">${tx.amount}</td>
      `;
      mempoolTable.appendChild(row);
    });
  } catch (err) {
    console.error("Error loading mempool:", err);
  }
}

// call both dashboard + mempool refresh every 3s
setInterval(() => {
  refreshDashboard();
  refreshMempool();
}, 3000);

// =====================
//START SIMULATION
// =====================
const startbtn = document.getElementById("startbtn");
if (startbtn) {
  startbtn.addEventListener("click", () => {
    window.location.href = "dashboard.html";
  });
}


// =====================
//LOGS PAGE
// =====================
const logsbtn = document.getElementById("logsbtn");
if (logsbtn) {
  logsbtn.addEventListener("click", () => {
    window.location.href = "logs_samp.html";
  });
}
// =====================
//Retrun to Dashboard PAGE
// =====================
const retbtn = document.getElementById("returnlog");
if (retbtn) {
  retbtn.addEventListener("click", () => {
    window.location.href = "dashboard.html";
  });
}
const ret_btn = document.getElementById("returndasboard");
if (ret_btn) {
  ret_btn.addEventListener("click", () => {
    window.location.href = "dashboard.html";
  });
}

const logs_btn = document.getElementById("return_log");
if (logs_btn) {
  logs_btn.addEventListener("click", () => {
    window.location.href = "log.html";
  });
}
const transaction_btn = document.getElementById("return_transaction");
if (transaction_btn) {
  transaction_btn.addEventListener("click", () => {
    window.location.href = "transaction.html";
  });
}


