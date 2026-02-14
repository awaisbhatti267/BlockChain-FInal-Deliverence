import csv
import glob
import os

# Absolute path to the directory this script is in
BASE = os.path.dirname(__file__)

# Pattern for log files (inside backend/data/)
LOG_FILES = glob.glob(os.path.join(BASE, "logs_*.csv"))

# Output file path
OUT = os.path.join(BASE, "combined_logs.csv")

print("Merging logs from:", LOG_FILES)
print("Saving to:", OUT)

with open(OUT, "w", newline='') as out:
    writer = csv.writer(out)
    writer.writerow(["timestamp", "txid", "sender", "receiver", "amount", "type"])

    for file in LOG_FILES:
        with open(file, "r") as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
            for row in reader:
                writer.writerow(row)

print("✔ DONE: combined_logs.csv generated!")
