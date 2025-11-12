import re, os
from datetime import datetime
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Tolerant Nginx "combined" format
LOG_PATTERN = re.compile(
    r'^(?P<ip>\S+)\s+\S+\s+\S+\s+\[(?P<ts>[^\]]+)\]\s+'
    r'"(?P<method>\S+)\s+(?P<path>\S+)\s+(?P<proto>[^"]+)"\s+'
    r'(?P<status>\d{3})\s+(?P<bytes>(?:\d+|-))\s+"[^"]*"\s+"(?P<ua>[^"]*)"$'
)

def parse_line(line: str):
    m = LOG_PATTERN.match(line.strip())
    if not m:
        return None
    # Example ts: 10/Nov/2025:10:21:34 +0530 → drop timezone for parsing
    ts_main = m.group("ts").split(" ")[0]
    ts = datetime.strptime(ts_main, "%d/%b/%Y:%H:%M:%S")
    bytes_field = m.group("bytes")
    bytes_sent = 0 if bytes_field == "-" else int(bytes_field)
    return {
        "client_ip": m.group("ip"),
        "timestamp": ts,
        "request_path": m.group("path"),
        "status": int(m.group("status")),
        "bytes_sent": bytes_sent,
        "user_agent": m.group("ua"),
    }

def main():
    raw_path = os.path.join("data", "raw", "nginx_access.log")
    if not os.path.exists(raw_path):
        raise FileNotFoundError(f"Log file not found: {raw_path}")

    out_root = os.path.join("data", "processed")
    os.makedirs(out_root, exist_ok=True)

    rows = []
    with open(raw_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line.strip():
                continue
            rec = parse_line(line)
            if rec:
                rows.append(rec)

    if not rows:
        print("No valid rows parsed. Check log format.")
        return

    df = pd.DataFrame(rows)
    # --- add these lines right after df = pd.DataFrame(rows)
    assert len(df) > 0, "No rows parsed"
    # validate HTTP status range
    assert df["status"].between(100, 599).all(), "Invalid HTTP status code detected in ETL"
    df["date"] = df["timestamp"].dt.date.astype(str)
    df["hour"] = df["timestamp"].dt.strftime("%H")
    df["endpoint"] = df["request_path"].str.split("?", n=1).str[0]
    df["is_error"] = (df["status"] >= 400).astype(int)

    # Write partitioned Parquet by date
    for dt, part in df.groupby("date"):
        part_dir = os.path.join(out_root, f"date={dt}")
        os.makedirs(part_dir, exist_ok=True)
        file_path = os.path.join(part_dir, f"logs_{dt.replace('-', '')}.parquet")
        table = pa.Table.from_pandas(part, preserve_index=False)
        pq.write_table(table, file_path)
        print(f"Wrote {len(part)} rows -> {file_path}")

if __name__ == "__main__":
    main()
