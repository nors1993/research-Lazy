# AGENTS.md - AutoResearch Agent System

> Compact guidance for future OpenCode sessions. Read this first.

## Project Overview

- **Type**: Python 3.11 FastAPI web service (multi-agent research/writing system)
- **Entry**: `src/api/main.py` → FastAPI app serves frontend at `/`
- **Frontend**: Single `frontend/index.html` (SPA, likely Vue/JS)
- **Spec Reference**: `specs/001-auto-research-agent/`

## Developer Commands

```bash
# Install (with dev deps)
pip install -e ".[dev]"

# Run dev server
uvicorn src.api.main:app --reload

# Run tests
pytest

# Lint (E501 ignored, py311 target, line-length 100)
ruff check src/ tests/

# Type check (strict mode)
mypy src/
```

## Key Conventions

- **Python**: 3.11+ required (structural pattern matching, match/case, type hints)
- **Async**: All I/O is async (`async def`, `await`)
- **Logging**: `structlog` via `get_logger(__name__)`
- **Linting**: ruff with rules `E,F,W,I,N,UP,B,C4,SIM`; ignore E501 (line-length 100)
- **Type checking**: mypy strict mode, `ignore_missing_imports=true`
- **Testing**: pytest-asyncio with `asyncio_mode = auto` (no explicit `@pytest.mark.asyncio`)

## Architecture

### Core Components

```
src/
├── api/           # FastAPI routes, SSE streaming, schemas
├── agents/        # 4 agents: editor, investigator, writer, reviewer
├── agents_extended/  # patent_agent, paper_agent (extended agents)
├── workflow/      # State machine, executor, builder, retry, timeout
├── llm/          # Unified LLM adapter (OpenAI/Compatible/Anthropic/Azure/Ollama)
├── skills/        # Base, registry, patent_writer, paper_writer, docx_generator
├── storage/      # SQLAlchemy models, Redis cache
└── utils/        # Exceptions, logger, workspace, cleanup, template
```

### Workflows (defined in `src/workflow/builder.py`)

- **PAPER_WORKFLOW**: `paper_feasibility → paper_research → paper_drafting → paper_publishing`
- **PATENT_WORKFLOW**: `intent_analysis → patent_feasibility → patent_research → patent_drafting → patent_validation → patent_publishing`

### Nodes

- Standard nodes: `src/workflow/nodes/__init__.py` (IntentAnalysis, FeasibilityStudy, DeepResearch, Drafting, etc.)
- Extended nodes: `src/workflow/nodes/extended.py` (patent/paper specific with real agent calls)

## LLM Configuration

### Per-Agent Config (in `.env`)

Each agent has dedicated settings (EDITOR, INVESTIGATOR, WRITER, REVIEWER):
```env
EDITOR_PROVIDER=openai_compatible
EDITOR_MODEL=deepseek-v4-flash
EDITOR_API_KEY=sk-...
EDITOR_BASE_URL=https://api.deepseek.com
```

### Provider Mappings

- `openai_compatible` / `openai-compatible` → `LLMProvider.OPENAI_COMPATIBLE` (appends `/v1` to base_url)
- `anthropic` → `LLMProvider.ANTHROPIC`
- `azure` / `azure_openai` → `LLMProvider.AZURE_OPENAI`
- `ollama` → `LLMProvider.OLLAMA`

### Adapter Creation

`src/workflow/executor.py::create_agent_adapter()` reads per-agent config and creates adapter. Base URL normalization adds `/v1` suffix for compatible providers.

## Skills System

- **Registry**: `src/skills/registry.py::SkillRegistry`
- **Base class**: `src/skills/base.py::BaseSkill`
- **Default skill paths**: `["F:/VsCode_projects/Research-skills/skills"]` (Windows-specific, hardcoded)
- **Registered skills**: patent_writer, paper_writer, docx_generator

## Environment Variables

```env
# App
APP_PORT=8000
DATABASE_URL=sqlite:///./autoresearch.db  # or postgresql://...
REDIS_URL=redis://localhost:6379/0

# LLM (fallback/default)
OPENAI_API_KEY=sk-...
OPENAI_COMPATIBLE_API_KEY=sk-...
OPENAI_COMPATIBLE_BASE_URL=https://api.deepseek.com
OPENAI_COMPATIBLE_MODEL=deepseek-v4-flash

# Workspace
WORKSPACE_TEMP_DIR=workspace/temp
WORKSPACE_OUTPUT_DIR=workspace/output
```

## SSE Streaming

Real-time progress via `GET /api/research/{task_id}/stream` (defined in `src/api/routes/stream.py`). Events: `node_start`, `node_complete`, `task_complete`, `task_failed`.

## Workspace File Saving

`src/utils/workspace.py::WorkspaceManager` handles temp/output dirs. **Warning**: `src/workflow/nodes/extended.py` has **hardcoded Windows path** (`F:/VsCode_projects/...`) - must fix for cross-platform.

## What Agents Often Miss

1. **Install**: `pip install -e ".[dev]"` required for dev dependencies
2. **Python version**: 3.11+ required (uses match/case, structural pattern matching)
3. **Provider enum**: `openai_compatible` maps to `LLMProvider.OPENAI_COMPATIBLE` (not `OPENAI`)
4. **Base URL**: Compatible adapter auto-appends `/v1` - don't add manually
5. **SSE format**: `yield f"data: {json.dumps(event)}\n\n"` - NOT double-prefixed with "data: "
6. **pytest-asyncio**: No decorator needed with `asyncio_mode = auto`
7. **mypy**: All imports must type-check; use `ignore_missing_imports=true` for external libs
8. **Hardcoded paths**: Extended nodes use Windows paths - fix before deploying to Linux
9. **Async lifespan**: FastAPI uses `@asynccontextmanager` for startup/shutdown (redis connect/disconnect)
10. **Skill registry**: Skills loaded from external Windows path - verify skill paths exist

## SpecKit Integration

```bash
/speckit.tasks  # Generate tasks from spec
/speckit.implement  # Execute implementation
```

Feature directory: `specs/001-auto-research-agent`