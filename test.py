import os
import json

def read_first_last_line(path):
    first_line = None
    last_line = None
    with open(path, "rb") as f:
        # First non-empty
        for line in f:
            line = line.strip()
            if line:
                first_line = json.loads(line)
                break
        if first_line is None:
            return None, None
            
        f.seek(-2, os.SEEK_END)
        while f.read(1) != b'\n':
            f.seek(-2, os.SEEK_CUR)
        last_line = f.readline().decode().strip()
        last_line = json.loads(last_line)
    return first_line, last_line

print(read_first_last_line("/Users/icmini/0luka/observability/logs/activity_feed.jsonl"))
