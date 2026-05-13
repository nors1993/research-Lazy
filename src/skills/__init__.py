"""Skills module for managing patent and paper writing capabilities."""

from .base import BaseSkill, PaperSkill, PatentSkill, SkillMetadata
from .docx_generator import DocxConfig, DocxGenerator, PaperDocxGenerator, PatentDocxGenerator
from .paper_writer import PaperWritingSkill
from .patent_writer import PatentWritingSkill
from .registry import SkillRegistry, skill_registry

__all__ = [
    "BaseSkill",
    "SkillMetadata",
    "PatentSkill",
    "PaperSkill",
    "SkillRegistry",
    "skill_registry",
    "DocxGenerator",
    "PatentDocxGenerator",
    "PaperDocxGenerator",
    "DocxConfig",
    "PatentWritingSkill",
    "PaperWritingSkill",
]
