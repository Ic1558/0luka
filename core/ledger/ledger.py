import hashlib
import os
import json
from datetime import datetime

LEDGER_PATH = "observability/stl/ledger/global_beacon.jsonl"

def sha256_msg(msg):
    return hashlib.sha256(msg.encode()).hexdigest()

def get_prev_hash():
    if not os.path.exists(LEDGER_PATH):
        return "0" * 64
    with open(LEDGER_PATH, 'rb') as f:
        try:
            f.seek(-2, os.SEEK_END)
            while f.read(1) != b'\n':
                f.seek(-2, os.SEEK_CUR)
        except OSError:
            f.seek(0)
        last_line = f.readline().decode()
        if not last_line: return "0" * 64
        entry = json.loads(last_line)
        return entry.get("this_beacon_hash", "0" * 64)

def ledger_append(event_type, payload):
    """
    Append an entry to the cryptographic ledger.
    """
    prev_hash = get_prev_hash()
    ts = datetime.now().astimezone().isoformat()
    
    # Create canonical entry
    entry = {
        "timestamp": ts,
        "event_type": event_type,
        "prev_beacon_hash": prev_hash,
        "payload": payload
    }
    
    entry_str = json.dumps(entry, sort_keys=True)
    this_hash = sha256_msg(entry_str)
    entry["this_beacon_hash"] = this_hash

    os.makedirs(os.path.dirname(LEDGER_PATH), exist_ok=True)
    with open(LEDGER_PATH, 'a') as f:
        f.write(json.dumps(entry, sort_keys=True) + '\n')
    
    print(f"DEBUG: Ledger COMMIT [{event_type}] hash={this_hash[:8]}")
    return this_hash
