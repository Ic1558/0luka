# Skill: NotebookLM (The Researcher)

---
name: notebooklm
version: 1.0
category: intelligence
owner: antigravity
sot: true
mandatory_read: NO
capabilities:
  filesystem: read
  process: exec
  network: scoped (NotebookLM API)
scope:
  - "~/0luka"
---

## 1. Identity
- **Role**: Intelligence Synthesis & Research Specialist.
- **Purpose**:
  - Leverage Google's NotebookLM for deep document analysis and creative synthesis.
  - Perform autonomous web and drive research to expand codebase knowledge.
  - Generate specialized artifacts (Audio, Video, Infographics, Reports) from project data.
  - Maintain session health through robust authentication management.

## 2. Contracts (Deterministic)

### Core Notebook Operations
| Tool | Description/Contract |
| :--- | :--- |
| `notebook_list` | List all available notebooks. |
| `notebook_create` | Create a new notebook with an optional title. |
| `notebook_get` | Retrieve full notebook details including source metadata. |
| `notebook_describe` | Get an AI-generated summary and suggested topics for a notebook. |
| `notebook_rename` | Update the title of an existing notebook. |
| `notebook_delete` | Permanently delete a notebook (requires `confirm=True`). |

### Source Management
| Tool | Description/Contract |
| :--- | :--- |
| `notebook_add_url` | Add a website or YouTube video as a source. |
| `notebook_add_text` | Add raw text content as a source. |
| `notebook_add_drive` | Add a Google Drive document (Doc, Slides, Sheet, PDF) as a source. |
| `source_describe` | Get AI-generated summary and keywords for a specific source. |
| `source_get_content` | Export raw text content from a source (high speed). |
| `source_list_drive` | Check freshness status of Drive-linked sources. |
| `source_sync_drive` | Sync stale Drive sources with latest content. |
| `source_delete` | Permanently delete a source from a notebook. |

### Research & Intelligence
| Tool | Description/Contract |
| :--- | :--- |
| `notebook_query` | Ask targeted questions against established sources. |
| `chat_configure` | Set specific goals or custom prompts for the notebook AI. |
| `research_start` | Launch "Deep" or "Fast" research tasks (Web/Drive). |
| `research_status` | Monitor the progress of ongoing research tasks. |
| `research_import` | Ingest completed research findings into the notebook. |

### Studio (Content Synthesis)
| Tool | Description/Contract |
| :--- | :--- |
| `audio_overview_create` | Generate podcasts/audio deep dives. |
| `video_overview_create` | Generate visual explainer videos in various styles. |
| `infographic_create` | Create structured visual representations of data. |
| `slide_deck_create` | Synthesize sources into presentation-ready slides. |
| `report_create` | Generate Briefing Docs, Study Guides, or Blog Posts. |
| `flashcards_create` | Create study aids from notebook content. |
| `quiz_create` | Generate interactive assessments. |
| `data_table_create` | Extract structured data into tabular format. |
| `mind_map_create` | Map relationships between notebook concepts. |
| `studio_status` | Retrieve status and URLs for generated artifacts. |
| `studio_delete` | Clean up studio artifacts. |

### System & Authentication
| Tool | Description/Contract |
| :--- | :--- |
| `refresh_auth` | Reload tokens or trigger headless re-auth. |
| `save_auth_tokens` | Manual token injection (Fallback method). |

## 3. Constraints (Fail-Closed)
- **Confirm Required**: Destructive actions (`delete`) and token-heavy operations (`sync`, `studio`) require explicit `confirm=True` after user review.
- **Scope**: Research is limited to authorized domains and Google Drive scopes.
- **Workflow**: Research MUST follow the `start` -> `status` -> `import` sequence.

## 4. Deterministic Execution Steps
1. **Discover**: Check if the notebook or source ID already exists.
2. **Authorize**: Ensure `refresh_auth` is called if session expires.
3. **Execute**: Submit task to NotebookLM MCP.
4. **Poll**: For long-running studio/research tasks, poll until complete.
5. **Verify**: Check `studio_status` or `notebook_get` for output evidence.

## 5. Failure Modes
- `AUTH_EXPIRED`: Requires `notebooklm-mcp-auth` manual intervention.
- `SOURCE_NOT_READY`: Attempting to query before indexing is complete.
- `SYNC_CONFLICT`: Drive permissions changed or file moved.
- `STUDIO_TIMEOUT`: Generation took longer than 300s.
