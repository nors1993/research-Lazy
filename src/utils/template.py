"""Template loader for custom document templates."""

from pathlib import Path

from .exceptions import ValidationException
from .logger import get_logger

logger = get_logger(__name__)


class TemplateLoader:
    """Loads and validates custom document templates."""

    SUPPORTED_EXTENSIONS = {".md", ".txt", ".html", ".tex"}

    def __init__(self, template_dir: str = "templates"):
        self.template_dir = Path(template_dir)
        self._template_cache: dict[str, str] = {}

    def load(self, template_path: str | None) -> str | None:
        """Load template content from file path."""
        if not template_path:
            return None

        # Check cache first
        if template_path in self._template_cache:
            logger.debug("template_cache_hit", path=template_path)
            return self._template_cache[template_path]

        # Validate path
        validated_path = self._validate_path(template_path)

        try:
            content = validated_path.read_text(encoding="utf-8")
            self._template_cache[template_path] = content
            logger.info("template_loaded", path=template_path)
            return content

        except FileNotFoundError:
            raise ValidationException(
                code="ERR_TEMPLATE_NOT_FOUND",
                message=f"Template file not found: {template_path}",
            )
        except UnicodeDecodeError:
            raise ValidationException(
                code="ERR_TEMPLATE_ENCODING",
                message=f"Template file encoding error: {template_path}",
            )

    def _validate_path(self, template_path: str) -> Path:
        """Validate template path is safe and allowed."""
        # Prevent directory traversal
        if ".." in template_path or template_path.startswith("/"):
            raise ValidationException(
                code="ERR_TEMPLATE_PATH_INVALID",
                message="Invalid template path",
            )

        # Check extension
        ext = Path(template_path).suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ValidationException(
                code="ERR_TEMPLATE_EXT_NOT_SUPPORTED",
                message=f"Template extension {ext} not supported. Supported: {self.SUPPORTED_EXTENSIONS}",
            )

        # Resolve full path
        full_path = Path(template_path)

        # If relative path, resolve from template_dir
        if not full_path.is_absolute():
            full_path = self.template_dir / template_path

        # Check file exists
        if not full_path.exists():
            raise ValidationException(
                code="ERR_TEMPLATE_NOT_FOUND",
                message=f"Template not found: {template_path}",
            )

        return full_path

    def clear_cache(self) -> None:
        """Clear template cache."""
        self._template_cache.clear()
        logger.info("template_cache_cleared")


# Global template loader
template_loader = TemplateLoader()
