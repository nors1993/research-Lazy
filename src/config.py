"""Application configuration using pydantic-settings."""

import os

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentLLMConfig:
    def __init__(
        self,
        provider: str = "openai",
        api_key: str = "",
        base_url: str = "",
        model: str = "gpt-4o",
        temperature: float = 0.7,
        max_tokens: int = 16384,
    ):
        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens


class AgentPromptConfig:
    def __init__(self, enabled: bool = False, prompt: str = ""):
        self.enabled = enabled
        self.prompt = prompt


class SystemPromptsConfig:
    def __init__(self, config_path: str = "agent_system_prompts.yaml"):
        self.config_path = config_path
        self.editor = AgentPromptConfig()
        self.investigator = AgentPromptConfig()
        self.writer = AgentPromptConfig()
        self.reviewer = AgentPromptConfig()
        self._load_config()

    def _load_config(self) -> None:
        if not os.path.exists(self.config_path):
            return
        try:
            with open(self.config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            for agent_name in ["editor", "investigator", "writer", "reviewer"]:
                if agent_name in data:
                    agent_data = data[agent_name]
                    setattr(
                        self,
                        agent_name,
                        AgentPromptConfig(
                            enabled=agent_data.get("enabled", False),
                            prompt=agent_data.get("prompt", ""),
                        ),
                    )
        except Exception:
            pass

    def get_prompt(self, agent_name: str) -> str:
        agent_config = getattr(self, agent_name.lower(), None)
        if agent_config and isinstance(agent_config, AgentPromptConfig) and agent_config.enabled:
            return agent_config.prompt
        return ""


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    app_env: str = Field(default="development", alias="APP_ENV")

    # Database - 默认为SQLite，生产环境使用PostgreSQL
    # 格式: sqlite:///./autoresearch.db 或 postgresql://user:pass@host:5432/db
    database_url: str = Field(
        default="sqlite:///./autoresearch.db",
        alias="DATABASE_URL",
    )

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        alias="REDIS_URL",
    )

    # LLM - OpenAI (default/fallback)
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")

    # LLM - OpenAI Compatible (custom base_url)
    openai_compatible_api_key: str = Field(default="", alias="OPENAI_COMPATIBLE_API_KEY")
    openai_compatible_base_url: str = Field(default="", alias="OPENAI_COMPATIBLE_BASE_URL")
    openai_compatible_model: str = Field(default="gpt-4o", alias="OPENAI_COMPATIBLE_MODEL")

    # LLM - Anthropic
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")

    # LLM - Azure OpenAI
    azure_openai_endpoint: str = Field(default="", alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_api_key: str = Field(default="", alias="AZURE_OPENAI_API_KEY")
    azure_openai_deployment: str = Field(default="gpt-4", alias="AZURE_OPENAI_DEPLOYMENT")

    # LLM - Ollama
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")

    # ============ Per-Agent LLM Configuration ============
    # Format: AGENT_PROVIDER, AGENT_API_KEY, AGENT_BASE_URL, AGENT_MODEL
    # Agents: editor, investigator, writer, reviewer

    # Editor Agent (Chief Orchestrator) - needs strong reasoning
    editor_provider: str = Field(default="openai_compatible", alias="EDITOR_PROVIDER")
    editor_api_key: str = Field(default="", alias="EDITOR_API_KEY")
    editor_base_url: str = Field(default="", alias="EDITOR_BASE_URL")
    editor_model: str = Field(default="deepseek-v4-flash", alias="EDITOR_MODEL")
    editor_temperature: float = Field(default=0.7, alias="EDITOR_TEMPERATURE")
    editor_max_tokens: int = Field(default=16384, alias="EDITOR_MAX_TOKENS")

    # Investigator Agent (Research) - needs good research capability
    investigator_provider: str = Field(default="openai_compatible", alias="INVESTIGATOR_PROVIDER")
    investigator_api_key: str = Field(default="", alias="INVESTIGATOR_API_KEY")
    investigator_base_url: str = Field(default="", alias="INVESTIGATOR_BASE_URL")
    investigator_model: str = Field(default="deepseek-v4-flash", alias="INVESTIGATOR_MODEL")
    investigator_temperature: float = Field(default=0.7, alias="INVESTIGATOR_TEMPERATURE")
    investigator_max_tokens: int = Field(default=16384, alias="INVESTIGATOR_MAX_TOKENS")

    # Writer Agent (Document Drafting) - needs good writing ability
    writer_provider: str = Field(default="openai_compatible", alias="WRITER_PROVIDER")
    writer_api_key: str = Field(default="", alias="WRITER_API_KEY")
    writer_base_url: str = Field(default="", alias="WRITER_BASE_URL")
    writer_model: str = Field(default="deepseek-v4-flash", alias="WRITER_MODEL")
    writer_temperature: float = Field(default=0.7, alias="WRITER_TEMPERATURE")
    writer_max_tokens: int = Field(default=16384, alias="WRITER_MAX_TOKENS")

    # Reviewer Agent (Logic Validation) - needs strong analysis
    reviewer_provider: str = Field(default="openai_compatible", alias="REVIEWER_PROVIDER")
    reviewer_api_key: str = Field(default="", alias="REVIEWER_API_KEY")
    reviewer_base_url: str = Field(default="", alias="REVIEWER_BASE_URL")
    reviewer_model: str = Field(default="deepseek-v4-flash", alias="REVIEWER_MODEL")
    reviewer_temperature: float = Field(default=0.7, alias="REVIEWER_TEMPERATURE")
    reviewer_max_tokens: int = Field(default=16384, alias="REVIEWER_MAX_TOKENS")

    # Workspace
    workspace_temp_dir: str = Field(
        default="workspace/temp", alias="WORKSPACE_TEMP_DIR"
    )
    workspace_output_dir: str = Field(
        default="workspace/output", alias="WORKSPACE_OUTPUT_DIR"
    )

    # Skills
    skill_paths: str = Field(
        default="skills", alias="SKILL_PATHS"
    )

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="json", alias="LOG_FORMAT")

    # System prompts config file path
    agent_prompts_file: str = Field(
        default="agent_system_prompts.yaml",
        alias="AGENT_PROMPTS_FILE",
    )

    # Cached system prompts config
    _system_prompts: SystemPromptsConfig | None = None

    @property
    def system_prompts(self) -> SystemPromptsConfig:
        if self._system_prompts is None:
            self._system_prompts = SystemPromptsConfig(self.agent_prompts_file)
        return self._system_prompts

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    def get_agent_system_prompt(self, agent_name: str) -> str:
        return self.system_prompts.get_prompt(agent_name)

    def get_agent_config(self, agent_name: str) -> AgentLLMConfig:
        """Get LLM configuration for a specific agent."""
        prefix = agent_name.lower()

        # Get provider
        provider = getattr(self, f"{prefix}_provider", "openai")
        if not provider:
            provider = "openai"

        # Get API key - first check agent-specific, then fallback to global
        api_key = getattr(self, f"{prefix}_api_key", "") or self.openai_api_key or self.openai_compatible_api_key

        # Get base_url - first check agent-specific
        base_url = getattr(self, f"{prefix}_base_url", "") or self.openai_compatible_base_url

        # Get model
        model = getattr(self, f"{prefix}_model", "gpt-4o")
        if not model:
            model = "gpt-4o"

        # Get temperature and max_tokens
        temperature = getattr(self, f"{prefix}_temperature", 0.7)
        max_tokens = getattr(self, f"{prefix}_max_tokens", 16384)

        return AgentLLMConfig(
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )


# Global settings instance
settings = Settings()
