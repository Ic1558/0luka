# NLP Control Plane Module

Natural language interface for 0luka task submission.

## Purpose

Enable chat-first interaction with 0luka without a frontend UI:
- Accept natural language commands
- Preview structured task specifications
- Confirm and submit tasks to execution queue
- Watch task state via telemetry

## Architecture

```
User Input → /preview → TaskSpec preview
          → /confirm → Drop file to interface/inbox/
          → /watch   → Poll telemetry for state
```

**CRITICAL**: This gateway does NOT execute tasks. It only:
1. Translates natural language to structured TaskSpec
2. Drops YAML files to the interface inbox
3. Reads telemetry for state updates

## Usage

### Start Server (Direct)
```bash
cd /Users/icmini/0luka
./runtime/venv/bin/python -m uvicorn modules.nlp_control_plane.app.main:app --port 8000
```

### Start Server (Via Shim)
```bash
cd /Users/icmini/0luka
./runtime/venv/bin/python -m uvicorn tools.web_bridge.main:app --port 8000
```

### CLI
```bash
/Users/icmini/0luka/tools/chatctl.zsh
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/chat/preview` | POST | Preview command as TaskSpec |
| `/api/v1/chat/confirm` | POST | Confirm and submit task |
| `/api/v1/chat/watch/{task_id}` | GET | Watch task state |
| `/api/v1/chat/stats` | GET | Session store statistics |

## Security

- NO subprocess/exec/eval calls
- Writes limited to `interface/inbox/`, `interface/pending_approval/`
- All actions logged to `observability/telemetry/gateway.jsonl`
- Author always server-injected as "gmx"
- Session TTL: 600s, Preview TTL: 300s
- Single-shot confirm (preview cannot be reused)

## Module Structure

```
nlp_control_plane/
├── __init__.py          # Module exports
├── manifest.yaml        # Module contract
├── requirements.txt     # Dependencies
├── README.md            # This file
├── app/
│   ├── main.py          # FastAPI app
│   └── routers/
│       └── chat.py      # Chat endpoints
├── core/
│   ├── session_store.py # Session management
│   ├── contracts.py     # Pydantic models
│   ├── normalizer.py    # NLP → TaskSpec
│   ├── task_writer.py   # File writing
│   ├── watcher.py       # Telemetry reading
│   └── guards.py        # Security enforcement
├── spec/
│   └── chat_control_plane_spec.md
└── tests/
    ├── test_normalizer.py
    └── test_api.py
```
