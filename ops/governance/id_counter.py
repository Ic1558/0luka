import os
import fcntl
from datetime import datetime

class IDCounter:
    def __init__(self, base_dir="/Users/icmini/0luka/observability/stl/state/counters"):
        self.base_dir = base_dir
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

    def get_next_tk(self):
        """Generates the next tk_key (YYMMDD_HHMMSS_SEQ)."""
        now = datetime.now()
        yymmdd = now.strftime("%y%m%d")
        seq_file = os.path.join(self.base_dir, f"{yymmdd}.seq")
        
        # Ensure file exists
        if not os.path.exists(seq_file):
            with open(seq_file, 'w') as f:
                f.write("0")
        
        # Atomic increment using flock
        with open(seq_file, 'r+') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            content = f.read().strip()
            seq = int(content) if content else 0
            seq += 1
            f.seek(0)
            f.write(str(seq))
            f.truncate()
            fcntl.flock(f, fcntl.LOCK_UN)
            
        return f"{yymmdd}_{seq:06d}"

if __name__ == "__main__":
    counter = IDCounter()
    print(counter.get_next_tk())
