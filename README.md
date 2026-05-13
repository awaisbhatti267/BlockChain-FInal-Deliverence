=========================================================
 DoubleForge: Blockchain Attack Testing Final Deliverance
=========================================================

This project demonstrates a blockchain simulation with 
transaction processing, P2P network, and double-spending 
attack scenarios. It integrates SimBlock (Java) with a 
Python backend for visualization and reporting.

----------------------------------------------------
1. TECHNOLOGIES USED
----------------------------------------------------
Languages:
- Python 3.10+  (backend, parser, prototype logic)
- Java (SimBlock simulator core)
- HTML, CSS, JavaScript (frontend dashboard)

Libraries (Python):
- Flask              (REST API for nodes)
- Flask-CORS         (CORS support for frontend requests)
- Requests           (HTTP peer-to-peer calls between nodes)
- hashlib / json / csv (standard libraries for parsing)
- matplotlib (optional, for visualizations in report) Final Visualization on Final Deliverance

Libraries (Java):
- SimBlock (modified simulator from source)

Tools & IDEs:
- Visual Studio Code (recommended for editing frontend/backend)
----------------------------------------------------
2. REQUIRED PLUGINS (VS Code)
----------------------------------------------------
- Python Extension (Microsoft)
- Java Extension Pack (for SimBlock if needed)
- Java JDK-8u202-windows-x64 (Download Link) https://www.oracle.com/java/technologies/javase/javase8-archive-downloads.html
- Live Server (optional, for frontend testing)


----------------------------------------------------
3. HOW TO RUN THE PROTOTYPE
----------------------------------------------------

STEP 1: Backend Node Simulation
--------------------------------
1. Open terminal in:
   E:\Awais\Virtual Uni\FYP\Prototype\backend  (Your Stored Folder)

2. Run the launcher to start 3 blockchain nodes:
   > python node_launcher.py

3. You should see:
   "✅ Peers registered. Nodes running. To stop, press Ctrl-C."

4. Nodes expose REST endpoints:
   - http://127.0.0.1:5001
   - http://127.0.0.1:5002
   - http://127.0.0.1:5003

Logs will stream automatically via `/logs` endpoint.

STEP 2: Frontend Dashboard
---------------------------
1. Open "Front-End/log.html" in browser (or run via Live Server).
2. The dashboard connects to Node 5001 for logs.
3. You can:
   - Create transactions
   - Arm attacks
   - View live execution logs in "Logs" page.

STEP 3: SimBlock Integration & JSON Output
------------------------------------------
1. Run SimBlock simulator (Java):
   > cd E:\Awais\Virtual Uni\FYP\Prototype\simblock-master\simulator    (Your Stored Folder)
   > mvn compile exec:java

2. Simulation results are saved to:
   E:\Awais\Virtual Uni\FYP\Prototype\simblock-master\simulator\src\dist\output\output.json    (Your Stored Folder)

STEP 4: Parsing Simulation Logs
--------------------------------
1. Open terminal in:
   E:\Awais\Virtual Uni\FYP\Prototype\simblock-master\simulator\src\dist\output    (Your Stored Folder)

2. Run parser:
   > python parse_simblock_tx_logs.py output.json

3. Generated files:
   - tx_summary.csv   (transaction list with realistic txids + attacker tag)
   - block_summary.csv (block heights and tx counts)

----------------------------------------------------
4. SAMPLE LOG OUTPUT (Frontend)
----------------------------------------------------
[INFO] Transaction TX1234 created  
[WARNING] Fork detected at block #15  
[ERROR] Double-spending attempt blocked  
[DEBUG] Node 2 broadcasted new block  
[INFO] Network reset successfully  

----------------------------------------------------
5. SAMPLE CSV (tx_summary.csv)
----------------------------------------------------
file,line_no,time,txid,from,to,amount,attacker
output.json,0,185,a1b2c3...,Alice,Bob,10,NO
output.json,1,233,d4e5f6...,Attacker,Bob,50,YES
...



----------------------------------------------------
6. TROUBLESHOOTING
----------------------------------------------------
❌ Problem: "⚠️ Node XXXX did not start within timeout"
✔️ Fix: Increase timeout in node_launcher.py (change 30 → 60 sec).
   Ensure no other process is using the same port (5001–5003).

❌ Problem: "UnicodeEncodeError: 'charmap' codec can't encode character"
✔️ Fix: In app.py logging, force UTF-8:
   sys.stdout.reconfigure(encoding="utf-8")

❌ Problem: Frontend logs not refreshing
✔️ Fix: Check CORS headers in Flask app. Restart with:
   flask run --reload --port=5001

❌ Problem: SimBlock output.json is empty
✔️ Fix: Make sure mvn compile exec:java runs without error.
   Check that simulation config in SimBlock (parameters.json) generates transactions.

❌ Problem: Peers not connected
✔️ Fix: Run node_launcher.py from backend folder, not inside subfolders.
   Verify requests library is installed:
   > pip install requests

❌ Problem: CSV not generated
✔️ Fix: Run parser from inside output/ folder where output.json exists:
   > python parse_simblock_tx_logs.py output.json

----------------------------------------------------
NOTES
----------------------------------------------------
- Run backend (Python nodes) before opening frontend.
- Run SimBlock separately to regenerate output.json for parsing.
- Parser produces clean CSVs for report/analysis.
- Ensure Python 3.10+ and Java 8+ are installed.
