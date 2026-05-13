"""Settings API routes for configuration management."""

from pathlib import Path

import aiohttp
from fastapi import APIRouter, Body

from ..schemas import ModelSettingsRequest, WorkspaceSettingsRequest

router = APIRouter()


def get_env_file_path() -> Path:
    """Get the .env file path."""
    # Find .env in project root
    current_dir = Path(__file__).parent
    for _ in range(5):  # Look up to 5 levels
        env_file = current_dir / ".env"
        if env_file.exists():
            return env_file
        current_dir = current_dir.parent
    # Default to project root
    return Path(".env")


def read_env_file() -> dict[str, str]:
    """Read current .env file contents."""
    env_path = get_env_file_path()
    env_vars = {}

    if env_path.exists():
        with open(env_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()

    return env_vars


def write_env_file(env_vars: dict[str, str]) -> None:
    """Write updated .env file."""
    env_path = get_env_file_path()

    with open(env_path, 'w', encoding='utf-8') as f:
        for key, value in env_vars.items():
            if value:  # Only write non-empty values
                f.write(f"{key}={value}\n")
            else:
                f.write(f"# {key}=\n")


@router.get("/workspace")
async def get_workspace_settings():
    """Get workspace settings."""
    from ...config import settings

    return {
        "output_path": settings.workspace_output_dir,
        "temp_path": settings.workspace_temp_dir,
    }


@router.post("/workspace")
async def update_workspace_settings(req: WorkspaceSettingsRequest):
    """Update workspace settings."""
    env_vars = read_env_file()

    if req.output_path:
        env_vars["WORKSPACE_OUTPUT_DIR"] = req.output_path

    if req.temp_path:
        env_vars["WORKSPACE_TEMP_DIR"] = req.temp_path

    write_env_file(env_vars)

    return {"status": "success", "message": "Workspace settings updated. Restart required."}


@router.get("/model")
async def get_model_settings():
    """Get current model configuration (masked)."""
    from ...config import settings

    # Return masked values for security
    def mask_key(key: str) -> str:
        if len(key) <= 4:
            return "*" * len(key)
        return key[:2] + "*" * (len(key) - 4) + key[-2:]

    return {
        "provider": "openai_compatible",  # Current default
        "base_url": settings.openai_compatible_base_url if settings.openai_compatible_base_url else settings.openai_compatible_base_url,
        "model": settings.openai_compatible_model,
        "api_key": mask_key(settings.openai_compatible_api_key) if settings.openai_compatible_api_key else "",
    }


@router.post("/model")
async def update_model_settings(req: ModelSettingsRequest):
    """Update model configuration."""
    env_vars = read_env_file()

    if req.base_url:
        env_vars["OPENAI_COMPATIBLE_BASE_URL"] = req.base_url

    if req.api_key:
        env_vars["OPENAI_COMPATIBLE_API_KEY"] = req.api_key

    if req.model:
        env_vars["OPENAI_COMPATIBLE_MODEL"] = req.model

    write_env_file(env_vars)

    return {"status": "success", "message": "Model settings updated. Restart required for changes to take effect."}


@router.get("/config")
async def get_all_settings():
    """Get all settings (masked)."""
    from ...config import settings

    def mask_key(key: str) -> str:
        if not key:
            return ""
        if len(key) <= 4:
            return "*" * len(key)
        return key[:2] + "*" * (len(key) - 4) + key[-2:]

    return {
        "workspace": {
            "output_path": settings.workspace_output_dir,
            "temp_path": settings.workspace_temp_dir,
        },
        "model": {
            "provider": "openai_compatible",
            "base_url": settings.openai_compatible_base_url,
            "model": settings.openai_compatible_model,
            "api_key": mask_key(settings.openai_compatible_api_key),
        }
    }


# 预设的模型列表（常用模型）
PRESET_MODELS = [
    {"id": "gpt-4o", "name": "GPT-4o"},
    {"id": "gpt-4o-mini", "name": "GPT-4o Mini"},
    {"id": "gpt-4-turbo", "name": "GPT-4 Turbo"},
    {"id": "gpt-4", "name": "GPT-4"},
    {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo"},
    {"id": "deepseek-v4-flash", "name": "DeepSeek V4 Flash"},
    {"id": "deepseek-chat", "name": "DeepSeek Chat"},
    {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet"},
    {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus"},
    {"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku"},
    {"id": "qwen-plus", "name": "Qwen Plus"},
    {"id": "qwen-turbo", "name": "Qwen Turbo"},
    {"id": "moonshot-v1-8k", "name": "Moonshot V1 8K"},
    {"id": "moonshot-v1-32k", "name": "Moonshot V1 32K"},
    {"id": "glm-4-flash", "name": "GLM-4 Flash"},
    {"id": "glm-4-plus", "name": "GLM-4 Plus"},
]


@router.get("/models")
async def get_available_models(base_url: str = "", api_key: str = ""):
    """Get list of available models."""
    from ...config import settings

    # 如果前端传入了参数，使用前端参数；否则使用后端配置
    test_base_url = base_url or settings.openai_compatible_base_url
    test_api_key = api_key or settings.openai_compatible_api_key

    models = []

    # 如果配置了有效的 API，尝试从 API 获取模型列表
    if test_base_url and test_api_key:
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {test_api_key}"}
                async with session.get(
                    f"{test_base_url.rstrip('/')}/models",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if "data" in data:
                            for m in data["data"]:
                                models.append({
                                    "id": m.get("id", ""),
                                    "name": m.get("id", "")
                                })
        except Exception:
            pass

    # 如果无法从 API 获取，使用预设列表
    if not models:
        models = PRESET_MODELS

    return {"models": models}


@router.post("/model/test")
async def test_model_connection(
    base_url: str = Body(default=""),
    api_key: str = Body(default=""),
    model: str = Body(default="")
):
    """Test model connection and return status."""
    from ...config import settings

    # 使用传入的参数或当前配置

    # 使用传入的参数或当前配置
    test_base_url = base_url or settings.openai_compatible_base_url
    test_api_key = api_key or settings.openai_compatible_api_key
    test_model = model or settings.openai_compatible_model

    if not test_base_url or not test_api_key:
        return {
            "status": "error",
            "message": "请配置 API Base URL 和 API Key",
            "latency_ms": 0
        }

    try:
        import time

        start_time = time.time()

        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {test_api_key}",
                "Content-Type": "application/json"
            }

            # 发送简单的测试请求
            payload = {
                "model": test_model,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 5
            }

            async with session.post(
                f"{test_base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                latency_ms = int((time.time() - start_time) * 1000)

                if resp.status == 200:
                    if latency_ms < 1000:
                        return {
                            "status": "success",
                            "message": "连接正常",
                            "latency_ms": latency_ms
                        }
                    else:
                        return {
                            "status": "warning",
                            "message": "连接正常，但延迟较高",
                            "latency_ms": latency_ms
                        }
                else:
                    error_text = await resp.text()
                    return {
                        "status": "error",
                        "message": f"API 返回错误: {resp.status}",
                        "latency_ms": latency_ms,
                        "detail": error_text[:200]
                    }

    except aiohttp.ClientConnectorError:
        return {
            "status": "error",
            "message": "无法连接到服务器",
            "latency_ms": 0
        }
    except TimeoutError:
        return {
            "status": "error",
            "message": "连接超时",
            "latency_ms": 0
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"连接失败: {str(e)[:100]}",
            "latency_ms": 0
        }
