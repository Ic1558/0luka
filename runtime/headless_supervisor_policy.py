"""AG-69: Headless Runtime Supervisor policy."""

SUPERVISOR_VERSION = "1.0"
CHECK_INTERVAL_SECONDS = 30
WATCHED_SERVICES = ["mcs", "chain_runner"]
PLIST_DIR = "ops/launchd"
