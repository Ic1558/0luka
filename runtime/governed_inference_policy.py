"""AG-70: Governed Inference Fabric policy."""

INFERENCE_VERSION = "1.0"

PROVIDERS = ["claude", "openai", "local", "mock"]
DEFAULT_PROVIDER = "mock"

ROUTING_CRITERIA = ["cost", "latency", "risk"]

# Risk levels that block certain providers
HIGH_RISK_BLOCKED_PROVIDERS: list = []
