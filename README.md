# AutoResearch Agent System

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.109-blue?logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
</p>

> An autonomous multi-agent research and writing system that orchestrates specialized AI agents to automatically produce polished academic papers and patent applications.

## Overview

AutoResearch Agent System is a Python 3.11+ FastAPI web application that coordinates a team of specialized AI agents — Editor, Investigator, Writer, and Reviewer — to autonomously conduct research and compose structured documents. The system supports configurable workflows (paper and patent), real-time SSE progress streaming, checkpoint-based pause/resume, template injection, and multiple LLM backends (OpenAI, Anthropic, Azure, Ollama, and any OpenAI-compatible provider).

A hosted frontend SPA at `/` provides a dark-mode dashboard for task creation, live progress tracking, and output download.

## Key Features

- **Configurable Multi-Agent Workflows**
  - **Paper Workflow** (5 stages): Feasibility → Research → Drafting → Validation → Publishing
  - **Patent Workflow** (6 stages): Intent Analysis → Feasibility → Research → Drafting → Validation → Publishing

- **4 Specialized AI Agents**
  - **Editor**: Central orchestrator — parses intent, delegates to sub-agents, makes strategic decisions (continue/retry/early-exit), performs de-AI polishing
  - **Investigator**: Feasibility assessment with structured JSON output, zero-hallucination literature review
  - **Writer**: Full document drafting following academic/patent structural templates
  - **Reviewer**: Multi-dimensional validation scoring (logic, plagiarism, innovation, completeness)

- **Real-Time Progress Streaming**: Server-Sent Events (SSE) at `/api/research/{task_id}/stream` — live `node_start`, `node_complete`, `task_complete` events

- **Pause/Resume with Checkpoints**: State machine persisted via checkpoint manager for task suspension and recovery

- **Template System**: Supports custom document templates, uploaded attachments (.docx, .pdf, .md), and temporary prompts

- **Multi-Provider LLM Backend**
  - OpenAI, OpenAI-compatible (any custom endpoint), Anthropic, Azure OpenAI, Ollama (local)
  - Per-agent provider/model/temperature configuration via environment variables

- **Structured Output**: Final documents generated as professional `.docx` files with proper formatting (A4, fonts, headings, margins)

- **Extended Agents**
  - **PatentAgent**: CNIPA-standard invention patent drafting with claim-first methodology, trinity validation (problem→solution→effect), and multi-embodiment support
  - **PaperAgent**: Academic paper drafting with 5-sentence abstract formula, anti-truncation enforcement, and multi-format support (IEEE, Nature, Elsevier)

- **Skill System**: Pluggable skill registry with `PaperWritingSkill`, `PatentWritingSkill`, and `DocxGenerator` for reusable domain expertise

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       FastAPI Layer                               │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────┐ ┌────────────┐  │
│  │   Research   │ │   Stream     │ │ Settings │ │   Health   │  │
│  │   Routes     │ │  (SSE/WS)    │ │  Routes  │ │  Routes    │  │
│  └──────────────┘ └──────────────┘ └──────────┘ └────────────┘  │
│  ┌──────────────┐ ┌──────────────┐                               │
│  │   Schemas    │ │ Event Storage│                               │
│  └──────────────┘ └──────────────┘                               │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                      Workflow Engine                              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────────┐  │
│  │State Machine │ │  Checkpoint  │ │  Builder (Node Sequence)  │  │
│  │ (retry/time) │ │  Manager     │ │  PAPER / PATENT          │  │
│  └──────────────┘ └──────────────┘ └──────────────────────────┘  │
│                        │                                         │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                    Workflow Nodes                            │  │
│  │  IntentAnalysis → FeasibilityStudy → DeepResearch →         │  │
│  │  Drafting → LogicValidation → PlagiarismCheck →             │  │
│  │  Polishing → Publishing                                     │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                       Agent Layer                                 │
│  ┌──────────┐ ┌──────────────┐ ┌──────────┐ ┌────────────────┐  │
│  │  Editor  │ │ Investigator │ │  Writer  │ │   Reviewer     │  │
│  │(Orchestr)│ │  (Research)  │ │(Drafting)│ │  (Validation)  │  │
│  └──────────┘ └──────────────┘ └──────────┘ └────────────────┘  │
│  ┌──────────────┐ ┌──────────────┐                               │
│  │ PatentAgent  │ │  PaperAgent  │  (Extended Agents)            │
│  └──────────────┘ └──────────────┘                               │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                     LLM Adapters                                  │
│  ┌──────┐ ┌──────────────────┐ ┌─────────┐ ┌───────┐ ┌──────┐  │
│  │OpenAI│ │OpenAI Compatible │ │Anthropic│ │ Azure │ │Ollama│  │
│  └──────┘ └──────────────────┘ └─────────┘ └───────┘ └──────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                   Storage & Skills                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────────┐  │
│  │SQLAlchemy│ │  Redis   │ │  Skill   │ │   Docx Generator  │  │
│  │  Models  │ │  Cache   │ │ Registry │ │  (Patent / Paper) │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Workflows

### Paper Workflow (PAPER_WORKFLOW)

| Node | Description | Timeout |
|---|---|---|
| `paper_feasibility` | Assess research viability, originality, and risk | 120s |
| `paper_research` | Deep literature review with synthesis and gap analysis | 300s |
| `paper_drafting` | Full academic paper draft (Intro→Methodology→Results→Conclusion) | 600s |
| `paper_validation` | Logic validation, plagiarism check, de-AI polishing | 120s |
| `paper_publishing` | Final .docx generation and output | 30s |

### Patent Workflow (PATENT_WORKFLOW)

| Node | Description | Timeout |
|---|---|---|
| `intent_analysis` | Parse user intent, extract domain and constraints | 60s |
| `patent_feasibility` | Prior art assessment, novelty scoring, risk evaluation | 120s |
| `patent_research` | Patent landscape search, related work identification | 300s |
| `patent_drafting` | CNIPA-standard patent drafting (claim-first methodology) | 600s |
| `patent_validation` | Logical consistency, lexical support, and claim mapping | 120s |
| `patent_publishing` | Final .docx generation and output | 30s |

## Agent System

### Core Agents

| Agent | Role | Key Responsibilities |
|---|---|---|
| **Editor** | Chief Orchestrator | Intent parsing, task delegation, strategic decisions (continue/retry/early-exit), de-AI polishing, publishing |
| **Investigator** | Research Strategist | Feasibility study (structured JSON), zero-hallucination literature review, gap analysis |
| **Writer** | Academic Writer | Strict structural drafting, anti-truncation, anti-hallucination grounding in investigator data |
| **Reviewer** | Logic Judge | Multi-dimension scoring (logic, plagiarism, innovation, completeness), actionable directives |

### Extended Agents

| Agent | Description | Standards |
|---|---|---|
| **PatentAgent** | End-to-end patent drafting with CNIPA compliance | Trinity validation (problem→solution→effect), Claim-First, 2-3 embodiments, lexical consistency |
| **PaperAgent** | End-to-end academic paper drafting with anti-AI tone | 5-sentence abstract formula, figure directives, multi-format templates |

## Supported LLM Providers

| Provider | Config Key | Notes |
|---|---|---|
| OpenAI | `OPENAI_API_KEY` | Standard GPT models |
| OpenAI-Compatible | `OPENAI_COMPATIBLE_API_KEY`, `OPENAI_COMPATIBLE_BASE_URL` | Works with any OpenAI-compatible endpoint (e.g., DeepSeek, Groq, vLLM). Base URL auto-appends `/v1`. |
| Anthropic | `ANTHROPIC_API_KEY` | Claude models |
| Azure OpenAI | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY` | Azure deployment |
| Ollama | `OLLAMA_BASE_URL` | Local models |

Each agent can be configured independently with its own provider, model, API key, temperature, and max tokens via environment variables (`EDITOR_*`, `INVESTIGATOR_*`, `WRITER_*`, `REVIEWER_*`).

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL (recommended) or SQLite
- Redis (optional, for caching)
- An LLM API key (at minimum, an OpenAI-compatible endpoint)

### Installation

```bash
# Clone repository
git clone <repo-url>
cd research-lazy

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"
```

### Configuration

Copy `.env.example` to `.env` and configure your LLM providers:

```bash
cp .env.example .env
```

Minimal configuration (using an OpenAI-compatible provider):

```env
# LLM Configuration
OPENAI_COMPATIBLE_API_KEY=sk-your-key
OPENAI_COMPATIBLE_BASE_URL=https://api.openai.com/v1
OPENAI_COMPATIBLE_MODEL=gpt-4o

# Optional — override per-agent
EDITOR_MODEL=gpt-4o
INVESTIGATOR_MODEL=gpt-4o
WRITER_MODEL=gpt-4o
REVIEWER_MODEL=gpt-4o
```

### Running

```bash
# Start development server
uvicorn src.api.main:app --reload --port 8000
```

Open http://localhost:8000 for the web dashboard.

### Running Tests

```bash
pytest

# Lint
ruff check src/ tests/

# Type check (strict)
mypy src/
```

## API Reference

### `POST /api/research/start`
Create and start a new research task.

**Request body:**
```json
{
  "topic": "Efficient attention mechanisms for long-sequence transformers",
  "domain": "CS",
  "docType": "PAPER",
  "requirements": "Focus on linear attention variants, include performance benchmarks"
}
```

### `GET /api/research/{task_id}/stream`
Subscribe to real-time SSE progress events.

**Events:** `connected`, `node_start`, `node_complete`, `task_complete`, `task_failed`, `task_stopped`

### `GET /api/research/{task_id}/status`
Check task status and output path.

### `POST /api/research/{task_id}/pause`
Pause a running task (checkpoint saved).

### `POST /api/research/{task_id}/resume`
Resume a paused task from the last checkpoint.

### `POST /api/research/{task_id}/cancel`
Cancel a running task.

### `POST /api/research/upload-template`
Upload a document template (.docx, .pdf, .md) — max 5 MB.

### `GET /api/settings/model`
Get current LLM configuration (keys masked).

### `GET /api/settings/workspace`
Get workspace path settings.

### `GET /health`
Health check endpoint.

## Project Structure

```
.
├── frontend/                    # Single-page application (Vue, dark theme)
│   └── index.html              # 2800+ line SPA dashboard
├── src/
│   ├── api/                    # FastAPI application
│   │   ├── main.py             # Entry point, lifespan, CORS, routers
│   │   ├── schemas.py          # Pydantic request/response schemas
│   │   ├── event_storage.py    # In-memory SSE event storage + cleanup
│   │   └── routes/
│   │       ├── health.py       # /health endpoint
│   │       ├── research.py     # Task CRUD, upload, start/pause/resume/cancel
│   │       ├── stream.py       # SSE streaming endpoint
│   │       └── settings.py     # LLM config + workspace settings
│   ├── agents/                 # Core AI agents
│   │   ├── base.py             # AgentRole, AgentConfig, AgentContext, BaseAgent
│   │   ├── editor.py           # EditorAgent — orchestrator
│   │   ├── investigator.py     # InvestigatorAgent — feasibility + research
│   │   ├── writer.py           # WriterAgent — drafting
│   │   └── reviewer.py         # ReviewerAgent — validation
│   ├── agents_extended/        # Domain-specific agents
│   │   ├── patent_agent.py     # PatentAgent — CNIPA patent drafting
│   │   └── paper_agent.py      # PaperAgent — academic paper drafting
│   ├── workflow/               # State machine and execution engine
│   │   ├── builder.py          # Workflow builder — node sequences + edge wiring
│   │   ├── executor.py         # Async executor — timeouts, per-agent LLM adapter creation
│   │   ├── state_machine.py    # StateMachine, WorkflowContext, NodeResult, NodeStatus
│   │   ├── checkpoint.py       # CheckpointManager — task serialization/resume
│   │   ├── timeout.py          # Timeout handler
│   │   ├── retry.py            # Retry logic
│   │   └── nodes/
│   │       ├── __init__.py     # Standard nodes (IntentAnalysis→Publishing)
│   │       └── extended.py     # Extended nodes (patent/paper with real agent calls)
│   ├── llm/                    # Unified LLM adapter
│   │   ├── adapter.py          # BaseLLMAdapter, LLMAdapter factory, LLMProvider enum
│   │   └── providers/          # Provider implementations
│   │       ├── openai.py
│   │       ├── anthropic.py
│   │       ├── azure.py
│   │       └── ollama.py
│   ├── skills/                 # Pluggable skill system
│   │   ├── base.py             # BaseSkill, SkillMetadata
│   │   ├── registry.py         # SkillRegistry — load, register, resolve references
│   │   ├── constants.py        # DocTypes, Domains, Fonts, Margins, AI patterns
│   │   ├── patent_writer.py    # PatentWritingSkill — CNIPA drafting
│   │   ├── paper_writer.py     # PaperWritingSkill — academic drafting
│   │   └── docx_generator.py   # DocxGenerator — formatted .docx output
│   ├── storage/                # Persistence
│   │   ├── models.py           # SQLAlchemy models (ResearchTask, AgentLog)
│   │   ├── cache.py            # Async Redis cache client
│   │   └── repositories/       # Data access layer
│   ├── utils/                  # Shared utilities
│   │   ├── logger.py           # structlog configuration
│   │   ├── exceptions.py       # Exception hierarchy (LLM, Network, Task)
│   │   ├── workspace.py        # WorkspaceManager — temp/output directories
│   │   ├── cleanup.py          # Temporary file cleanup
│   │   ├── document_parser.py  # Uploaded document parsing
│   │   └── template.py         # Template rendering
│   └── config.py               # pydantic-settings: env loading, per-agent config
├── specs/                      # Specification documents
│   └── 001-auto-research-agent/
├── tests/                      # Test suite (pytest-asyncio, asyncio_mode=auto)
│   ├── unit/
│   └── integration/
├── workspace/                  # Runtime workspace (temp + output)
│   ├── temp/                   # Per-task temporary files
│   └── output/                 # Generated documents
├── .env.example                # Environment configuration reference
├── agent_system_prompts.yaml   # Customizable system prompts per agent
├── pyproject.toml              # Project metadata, ruff, mypy, pytest config
└── AGENTS.md                   # Developer onboarding guide
```

## Tech Stack

| Component | Technology |
|---|---|
| **Runtime** | Python 3.11+ |
| **Web Framework** | FastAPI 0.109+ with Uvicorn |
| **API Validation** | Pydantic v2 + pydantic-settings |
| **Database ORM** | SQLAlchemy 2.0 (async) |
| **Cache** | Redis (async via redis-py) |
| **LLM Clients** | OpenAI SDK, Anthropic SDK, httpx (Ollama/Azure) |
| **Document Gen** | python-docx |
| **Logging** | structlog |
| **Frontend** | Vanilla JS SPA (dark theme, 2800+ lines) |
| **Testing** | pytest + pytest-asyncio (asyncio_mode=auto) |
| **Linting** | ruff (E,F,W,I,N,UP,B,C4,SIM) |
| **Type Checking** | mypy (strict mode) |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Lint
ruff check src/ tests/

# Type check (strict)
mypy src/

# Run dev server with hot reload
uvicorn src.api.main:app --reload
```

See `AGENTS.md` for detailed developer onboarding, architecture deep-dive, and convention reference.

## License

MIT
