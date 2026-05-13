"""Skill registry for managing available skills."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from .base import BaseSkill, SkillMetadata

from ..config import settings


@dataclass
class SkillReference:
    """Reference document for a skill."""

    name: str
    path: str
    content: str = ""


@dataclass
class RegisteredSkill:
    """Registered skill with metadata and references."""

    metadata: SkillMetadata
    skill_instance: BaseSkill
    references: dict[str, SkillReference] = field(default_factory=dict)
    prompt_templates: dict[str, str] = field(default_factory=dict)


class SkillRegistry:
    """Global registry for managing skills."""

    def __init__(self):
        self._skills: dict[str, RegisteredSkill] = {}
        paths = settings.skill_paths
        if isinstance(paths, str):
            self._skill_paths = [p.strip() for p in paths.split(",") if p.strip()]
        else:
            self._skill_paths = list(paths) if paths else []

    def add_search_path(self, path: str) -> None:
        """Add a path to search for skills."""
        if path not in self._skill_paths:
            self._skill_paths.append(path)

    def register_skill(self, name: str, skill: BaseSkill, references: dict[str, str] | None = None) -> None:
        """Register a skill with the registry."""
        skill_path = skill.metadata.skill_path or ""
        registered = RegisteredSkill(
            metadata=skill.metadata,
            skill_instance=skill,
            references=self._load_references(skill_path, references or {}),
        )
        self._skills[name] = registered

    def get_skill(self, name: str) -> BaseSkill | None:
        """Get a skill by name."""
        if name in self._skills:
            return self._skills[name].skill_instance
        return None

    def get_skill_metadata(self, name: str) -> SkillMetadata | None:
        """Get skill metadata by name."""
        if name in self._skills:
            return self._skills[name].metadata
        return None

    def get_skill_references(self, name: str) -> dict[str, str]:
        """Get all reference documents for a skill."""
        if name in self._skills:
            return {k: v.content for k, v in self._skills[name].references.items()}
        return {}

    def get_reference(self, skill_name: str, ref_name: str) -> str | None:
        """Get a specific reference document."""
        if skill_name in self._skills:
            if ref_name in self._skills[skill_name].references:
                return self._skills[skill_name].references[ref_name].content
        return None

    def list_skills(self) -> list[dict]:
        """List all registered skills."""
        return [
            {
                "name": name,
                "description": reg.metadata.description,
                "version": reg.metadata.version,
                "category": reg.metadata.category,
                "tags": reg.metadata.tags,
                "references": list(reg.references.keys()),
            }
            for name, reg in self._skills.items()
        ]

    def _load_references(self, skill_path: str, custom_refs: dict[str, str] | None = None) -> dict[str, SkillReference]:
        """Load reference documents for a skill."""
        refs = {}
        if not skill_path:
            custom_refs = custom_refs or {}
            for name, content in custom_refs.items():
                refs[name] = SkillReference(name=name, path="", content=content)
            return refs

        base_path = Path(skill_path).parent / "references"
        if base_path.exists():
            for ref_file in base_path.glob("*.md"):
                try:
                    content = ref_file.read_text(encoding="utf-8")
                    refs[ref_file.stem] = SkillReference(
                        name=ref_file.stem,
                        path=str(ref_file),
                        content=content,
                    )
                except Exception:
                    pass

        if custom_refs:
            for name, content in custom_refs.items():
                refs[name] = SkillReference(name=name, path="", content=content)

        return refs

    def load_skill_from_path(self, skill_dir: Path) -> BaseSkill | None:
        """Load a skill from a directory path."""
        from .base import BaseSkill, PaperSkill, PatentSkill

        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            return None

        try:
            content = skill_file.read_text(encoding="utf-8")
            metadata = self._parse_skill_metadata(content)
            metadata.skill_path = str(skill_dir)

            # Create appropriate skill instance
            if "patent" in skill_dir.name.lower():
                skill: BaseSkill = PatentSkill(metadata)
            elif "paper" in skill_dir.name.lower():
                skill = PaperSkill(metadata)
            else:
                # For unknown skills, create a wrapper
                class GenericSkill(BaseSkill):
                    async def execute(self, context):
                        return {"status": "completed"}

                skill = GenericSkill(metadata)

            self.register_skill(metadata.name, skill)
            return skill

        except Exception as e:
            print(f"Failed to load skill from {skill_dir}: {e}")
            return None

    def _parse_skill_metadata(self, content: str) -> SkillMetadata:
        """Parse skill metadata from SKILL.md content."""
        from .base import SkillMetadata

        # Extract YAML frontmatter
        yaml_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if yaml_match:
            try:
                data = yaml.safe_load(yaml_match.group(1))
                return SkillMetadata.from_dict(data)
            except Exception:
                pass

        return SkillMetadata(name="unknown", description="")

    def discover_skills(self) -> list[str]:
        """Discover and load all available skills."""
        discovered = []
        for base_path in self._skill_paths:
            path = Path(base_path)
            if not path.exists():
                continue

            for skill_dir in path.iterdir():
                if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                    skill = self.load_skill_from_path(skill_dir)
                    if skill:
                        discovered.append(skill.metadata.name)

        return discovered


# Global singleton
skill_registry = SkillRegistry()
