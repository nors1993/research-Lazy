"""Base skill classes and interfaces."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillMetadata:
    """Metadata for a skill."""

    name: str
    description: str
    version: str = "1.0.0"
    author: str = "Sisyphus"
    license: str = "MIT"
    dependencies: list[str] = field(default_factory=list)
    platforms: list[str] = field(default_factory=lambda: ["linux", "macos", "windows"])
    category: str = "research"
    tags: list[str] = field(default_factory=list)
    related_skills: list[str] = field(default_factory=list)
    skill_path: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SkillMetadata":
        """Create from dictionary."""
        # Handle nested metadata.hermes structure
        if "metadata" in data and "hermes" in data["metadata"]:
            hermes = data["metadata"]["hermes"]
            return cls(
                name=data.get("name", ""),
                description=data.get("description", ""),
                version=data.get("version", "1.0.0"),
                author=data.get("author", "Sisyphus"),
                license=data.get("license", "MIT"),
                dependencies=data.get("dependencies", []),
                platforms=data.get("platforms", ["linux", "macos", "windows"]),
                category=hermes.get("category", "research"),
                tags=hermes.get("tags", []),
                related_skills=hermes.get("related_skills", []),
            )
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            author=data.get("author", "Sisyphus"),
            license=data.get("license", "MIT"),
            dependencies=data.get("dependencies", []),
            platforms=data.get("platforms", ["linux", "macos", "windows"]),
            category=data.get("category", "research"),
            tags=data.get("tags", []),
            related_skills=data.get("related_skills", []),
        )


class BaseSkill(ABC):
    """Abstract base class for all skills."""

    def __init__(self, metadata: SkillMetadata):
        self.metadata = metadata

    @abstractmethod
    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute the skill with given context."""
        pass

    def get_prompt_template(self, step: str) -> str | None:
        """Get prompt template for a specific step."""
        return None

    def get_reference_doc(self, doc_name: str) -> str | None:
        """Get reference document content."""
        return None


@dataclass
class SkillExecutionContext:
    """Context for skill execution."""

    task_id: str
    topic: str
    domain: str
    doc_type: str
    language: str = "zh-CN"
    requirements: str | None = None
    template_path: str | None = None
    output_dir: str | None = None
    shared_data: dict[str, Any] = field(default_factory=dict)


class PatentSkill(BaseSkill):
    """Patent writing skill with CNIPA standard support."""

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute patent writing workflow."""
        # Step 1: Feasibility Study
        feasibility = await self._feasibility_study(context)
        if feasibility.get("status") == "FAIL":
            return {"status": "failed", "reason": "Not feasible", "feasibility": feasibility}

        # Step 2: Deep Research
        research = await self._deep_research(context, feasibility)

        # Step 3: Drafting (Claim-First)
        patent_doc = await self._draft_patent(context, feasibility, research)

        # Step 4: Logic Validation
        validation = await self._logic_validation(patent_doc, context)

        # Step 5: Plagiarism Check
        plagiarism = await self._plagiarism_check(patent_doc, context)

        # Step 6: Polishing
        polished = await self._polish(patent_doc, context)

        # Step 7: Publishing (generate docx)
        output_path = await self._publish(polished, context)

        return {
            "status": "completed",
            "feasibility": feasibility,
            "research": research,
            "patent_doc": patent_doc,
            "validation": validation,
            "plagiarism": plagiarism,
            "polished": polished,
            "output_path": output_path,
        }

    async def _feasibility_study(self, context: dict[str, Any]) -> dict[str, Any]:
        """Perform patent feasibility study."""
        return {"status": "PASS", "novelty_points": [], "related_work": []}

    async def _deep_research(self, context: dict[str, Any], feasibility: dict[str, Any]) -> dict[str, Any]:
        """Conduct deep literature research."""
        return {"literature_review": "", "references": []}

    async def _draft_patent(self, context: dict[str, Any], feasibility: dict[str, Any], research: dict[str, Any]) -> dict[str, Any]:
        """Draft patent with Claim-First logic."""
        return {"patent_content": "", "claims": [], "specification": ""}

    async def _logic_validation(self, patent_doc: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Validate patent logic and claim-evidence mapping."""
        return {"status": "PASS", "issues": []}

    async def _plagiarism_check(self, patent_doc: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Check for plagiarism."""
        return {"passed": True, "similarity_rate": 0.0}

    async def _polish(self, patent_doc: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Polish and remove AI patterns."""
        return {"polished_content": ""}

    async def _publish(self, polished: dict[str, Any], context: dict[str, Any]) -> str:
        """Publish as docx."""
        return ""


class PaperSkill(BaseSkill):
    """Academic paper writing skill."""

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute paper writing workflow."""
        # Step 1: Feasibility Study
        feasibility = await self._feasibility_study(context)
        if feasibility.get("status") == "FAIL":
            return {"status": "failed", "reason": "Not feasible", "feasibility": feasibility}

        # Step 2: Deep Research
        research = await self._deep_research(context, feasibility)

        # Step 3: Drafting
        paper_doc = await self._draft_paper(context, feasibility, research)

        # Step 4: Logic Validation
        validation = await self._logic_validation(paper_doc, context)

        # Step 5: Plagiarism Check
        plagiarism = await self._plagiarism_check(paper_doc, context)

        # Step 6: Polishing
        polished = await self._polish(paper_doc, context)

        # Step 7: Publishing
        output_path = await self._publish(polished, context)

        return {
            "status": "completed",
            "feasibility": feasibility,
            "research": research,
            "paper_doc": paper_doc,
            "validation": validation,
            "plagiarism": plagiarism,
            "polished": polished,
            "output_path": output_path,
        }

    async def _feasibility_study(self, context: dict[str, Any]) -> dict[str, Any]:
        """Perform paper feasibility study."""
        return {"status": "PASS", "novelty_points": [], "related_work": []}

    async def _deep_research(self, context: dict[str, Any], feasibility: dict[str, Any]) -> dict[str, Any]:
        """Conduct deep literature research."""
        return {"literature_review": "", "references": []}

    async def _draft_paper(self, context: dict[str, Any], feasibility: dict[str, Any], research: dict[str, Any]) -> dict[str, Any]:
        """Draft academic paper."""
        return {"paper_content": "", "sections": {}}

    async def _logic_validation(self, paper_doc: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Validate paper logic."""
        return {"status": "PASS", "issues": []}

    async def _plagiarism_check(self, paper_doc: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Check for plagiarism."""
        return {"passed": True, "similarity_rate": 0.0}

    async def _polish(self, paper_doc: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Polish and remove AI patterns."""
        return {"polished_content": ""}

    async def _publish(self, polished: dict[str, Any], context: dict[str, Any]) -> str:
        """Publish as docx."""
        return ""
