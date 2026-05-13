"""Paper Agent - specialized agent for academic paper writing workflow."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from ..agents.base import AgentConfig, AgentContext, AgentRole, BaseAgent
from ..llm.adapter import BaseLLMAdapter
from ..skills.constants import AI_PATTERNS_EN, AI_PATTERNS_ZH
from ..skills.docx_generator import PaperDocxGenerator
from ..skills.paper_writer import PaperContent, PaperWritingSkill
from ..utils.logger import get_logger

logger = get_logger(__name__)


PAPER_AGENT_SYSTEM_PROMPT = """You are an Academic Paper Writing Expert Agent. 
Your role is to orchestrate the complete academic paper writing workflow, enforcing rigorous academic standards, logical consistency, and zero-hallucination policies.

Workflow Steps & Directives:
1. Feasibility & Deep Research: Ensure the research gap is real and literature is strictly verifiable.
2. Paper Drafting: Execute the standard academic structure. [CRITICAL: Do NOT fabricate experimental data. If no data is provided, outline a rigorous "Experimental Design" or use placeholders (e.g., "[Insert Dataset Name]")].
3. Validation & Plagiarism: Verify that every claim maps strictly to cited evidence.
4. Polishing & Publishing: Eradicate AI-like tone and format for final .docx generation.

Standard Academic Structure & Constraints:
1. Title: Precise, action-oriented, not overly broad.
2. Abstract (Strict 5-Sentence Formula):
   - Sentence 1: What we achieved (The core contribution).
   - Sentence 2: Why it is hard and important (The research gap).
   - Sentence 3: How we do it (Methodology with specific technical keywords).
   - Sentence 4: What evidence we have (Dataset/Experimental setup).
   - Sentence 5: Our most remarkable result (Specific metric or comparative advantage).
3. Introduction: Must follow the funnel logic (Broad Context -> Specific Problem -> Limitations of Current Work -> Our Approach -> Explicit Bulleted Contributions).
4. Methodology: Must be reproducible. Detail the mathematical/logical formulations clearly.
5. Results & Discussion: Compare against specific baselines. Discussion must address limitations honestly.
6. Conclusion: Synthesize the impact; DO NOT just copy-paste the abstract.

Figure/Visual Directives (for empirical papers):
- explicitly indicate where to insert:
  [Figure 1: Overview/historical data]
  [Figure 2: Structural comparison]
  [Figure 3: Quantitative comparison]
  [Figure 4: Process/mechanism]

Data Currency & Grounding Rules:
- "Current status" uses data BEFORE specified time point; "Trends" uses data FROM specified time point. 
- ALWAYS annotate data cutoff dates.
- ALL citations must be factual.

Polishing & De-AIization Rules:
- Tone: Objective, authoritative, precise.
- BAN (zh-CN): "综上所述", "总而言之", "值得注意的是", "需要指出的是", "不可否认".
- BAN (en-US): "delve into", "it is important to note", "significantly", "testament", "tapestry", "in summary".
- ACTION: Replace passive voice with active academic phrasing (e.g., "This paper proposes..." instead of "In this paper, a method is proposed...").
"""


class PaperAgent(BaseAgent):
    """Agent specialized in academic paper writing."""

    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        max_tokens: int = 16384,
    ):
        config = AgentConfig(
            role=AgentRole.EDITOR,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=PAPER_AGENT_SYSTEM_PROMPT,
        )
        super().__init__(config, llm_adapter)
        self.paper_skill = None

    def _init_paper_skill(self) -> PaperWritingSkill:
        """Initialize paper writing skill with LLM adapter."""
        from ..skills.base import SkillMetadata

        metadata = SkillMetadata(
            name="paper-writing",
            description="Write research paper for any academic domain",
            category="research",
            tags=["paper", "academic", "research", "publication"],
        )

        skill = PaperWritingSkill(metadata)
        skill.set_llm_adapter(self.llm_adapter)
        return skill

    async def execute(self, context: AgentContext) -> dict[str, Any]:
        """Execute the paper writing workflow."""
        logger.info("paper_agent_executing", task_id=context.task_id, topic=context.topic)

        # Initialize skill
        self.paper_skill = self._init_paper_skill()

        # Prepare execution context
        exec_context = {
            "topic": context.topic,
            "language": context.language,
            "output_dir": getattr(context, "output_dir", ""),
            "requirements": context.requirements,
            "template_path": context.template_path,
            "domain": context.domain,
            "doc_type": context.doc_type,
            "target_format": getattr(context, "target_format", "General"),
        }

        # Execute full workflow
        result = await self.paper_skill.execute(exec_context)

        return {
            "status": result.get("status", "unknown"),
            "node": "paper_writing",
            "output_path": result.get("output_path"),
            "feasibility": result.get("feasibility"),
            "research": result.get("research"),
            "paper_content": result.get("paper_content"),
            "validation": result.get("validation"),
            "plagiarism": result.get("plagiarism"),
            "polished": result.get("polished"),
        }

    async def execute_workflow(
        self,
        context: AgentContext,
        feasibility_result: dict[str, Any] | None = None,
        research_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute workflow with pre-computed results."""
        logger.info("paper_workflow_execution", task_id=context.task_id)

        if not self.paper_skill:
            self.paper_skill = self._init_paper_skill()

        # If we have pre-computed results, use them directly
        if feasibility_result and research_result:
            # Generate paper from existing research
            paper_content = await self._draft_paper_from_research(
                context, feasibility_result, research_result
            )

            # Validation
            validation = await self._validate_logic(paper_content)

            # Plagiarism check
            plagiarism = await self._plagiarism_check(paper_content)

            # Polish
            language = context.language
            polished = await self._polish(paper_content, language)

            # Publish
            output_path = await self._publish(polished, context)

            return {
                "status": "completed",
                "paper_content": paper_content.__dict__,
                "validation": validation,
                "plagiarism": plagiarism,
                "polished": polished.__dict__,
                "output_path": output_path,
            }

        # Otherwise execute full workflow
        return await self.execute(context)

    async def _draft_paper_from_research(
        self,
        context: AgentContext,
        feasibility: dict[str, Any],
        research: dict[str, Any],
    ) -> PaperContent:
        """Draft paper using pre-computed feasibility and research results."""
        from ..skills.paper_writer import PaperContent

        language = context.language
        target_format = getattr(context, "target_format", "General")

        # Build user requirements section
        user_requirements = ""
        if context.requirements:
            user_requirements = f"""
User Requirements:
{context.requirements}
"""

        # Build template content section
        template_section = ""
        if context.template_content:
            template_section = f"""
Document Template Structure (must follow):
{context.template_content}
"""

        prompt = f"""Draft a complete academic paper following {target_format} format.

Topic: {context.topic}
Domain: {context.domain}
{user_requirements}{template_section}
Feasibility Study:
{self._format_feasibility(feasibility)}

Literature Review:
{research.get('literature_review', '')[:4000]}

References (at least 15):
{self._format_references(research.get('references', []))}

Research Gaps:
{self._format_list(research.get('research_gaps', []))}

Generate all sections of the paper with FULL content (no placeholders).

Output as JSON:
{{
    "title": "Paper Title",
    "abstract": "5-sentence abstract",
    "keywords": ["keyword1", "keyword2", ...],
    "sections": {{
        "introduction": "Full introduction...",
        "related_work": "Full related work by themes...",
        "methodology": "Full methodology enabling reimplementation...",
        "results": "Full results with data...",
        "discussion": "Full discussion...",
        "conclusion": "Full conclusion..."
    }},
    "figures": [],
    "tables": [],
    "references": [...]
}}

Language: {language}
Important: Output valid JSON only."""

        response = await self.generate_response(prompt)
        result = self._parse_json_response(response.content)

        return PaperContent(
            title=result.get("title", context.topic),
            abstract=result.get("abstract", ""),
            keywords=result.get("keywords", []),
            sections=result.get("sections", {}),
            figures=result.get("figures", []),
            tables=result.get("tables", []),
            references=research.get("references", []),
        )

    async def _validate_logic(self, paper: PaperContent) -> dict[str, Any]:
        """Validate paper logic."""
        section_items = []
        for k, v in paper.sections.items():
            if v:
                content = v if isinstance(v, str) else "\n".join(str(item) for item in v)
                section_items.append(f"## {k.upper()}\n{content[:300]}...")
        sections_text = "\n\n".join(section_items)

        prompt = f"""Validate the following paper for logical consistency:

Title: {paper.title}

Sections:
{sections_text}

Validation Checklist:
1. All claims have supporting evidence?
2. No logical contradictions between sections?
3. Consistent terminology throughout?
4. Methods enable reimplementation?
5. Results support conclusions?

Output as JSON:
{{
    "status": "PASS | FAIL | NEEDS_REVISION",
    "issues": [...],
    "statistics": {{
        "total_claims": N,
        "supported_claims": N
    }}
}}

Language: en-US"""

        response = await self.generate_response(prompt)
        return self._parse_json_response(response.content)

    async def _plagiarism_check(self, paper: PaperContent) -> dict[str, Any]:
        """Check for plagiarism."""
        key_text = f"""
        Title: {paper.title}
        Abstract: {paper.abstract}
        Introduction: {paper.sections.get('introduction', '')[:1000]}
        """

        prompt = f"""Estimate plagiarism risk for this paper:

{key_text}

Section-specific thresholds:
- Abstract: <10%
- Introduction: <20%
- Related Work: <30%
- Methodology: <15%
- Results: <10%
- Conclusion: <15%

Output as JSON:
{{
    "overall_similarity": 0.0-100.0,
    "status": "pass | needs_revision",
    "sections": [...],
    "recommendations": [...]
}}

Language: en-US"""

        response = await self.generate_response(prompt)
        return self._parse_json_response(response.content)

    async def _polish(self, paper: PaperContent, language: str) -> PaperContent:
        from ..skills.constants import remove_ai_patterns

        patterns = AI_PATTERNS_ZH if language == "zh-CN" else AI_PATTERNS_EN

        def clean(text):
            return remove_ai_patterns(text, patterns)

        cleaned_sections = {}
        for section_name, section_content in paper.sections.items():
            cleaned_sections[section_name] = clean(section_content)

        return PaperContent(
            title=clean(paper.title),
            abstract=clean(paper.abstract),
            keywords=paper.keywords,
            sections=cleaned_sections,
            figures=paper.figures,
            tables=paper.tables,
            references=paper.references,
        )

    async def _publish(self, paper: PaperContent, context: AgentContext) -> str:
        """Publish paper as .docx."""
        from pathlib import Path

        language = context.language

        # Generate output path
        date_str = datetime.now().strftime("%Y_%m_%d")
        safe_topic = re.sub(r"[^\w\u4e00-\u9fff\s-]", "", context.topic)[:30]
        suffix = "论文" if language == "zh-CN" else "paper"
        filename = f"{safe_topic}_{date_str}_{suffix}.docx"

        # Use workspace manager if available
        try:
            from ..utils.workspace import workspace_manager
            workspace_manager.initialize()
            workspace_manager.create_task_workspace(context.task_id)

            output_dir = Path(workspace_manager.get_task_workspace(context.task_id))
            output_path = output_dir / filename
        except Exception:
            output_path = Path.cwd() / filename

        # Generate docx
        generator = PaperDocxGenerator(language=language)
        generator.create_paper(
            title=paper.title,
            abstract=paper.abstract,
            keywords=paper.keywords,
            sections=paper.sections,
            references=paper.references,
            output_path=str(output_path),
        )

        return str(output_path)

    # Helper methods

    def _parse_json_response(self, response: str) -> dict[str, Any]:
        """Parse JSON from LLM response."""
        import json

        # Remove markdown code blocks
        response = re.sub(r"```json\s*", "", response)
        response = re.sub(r"```\s*$", "", response)

        if "{" in response:
            start = response.find("{")
            end = response.rfind("}") + 1
            json_str = response[start:end] if start >= 0 and end > start else response
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.warning("Failed to parse JSON from response", error=str(e), response_preview=response[:200])
                return {"error": "JSON parse failed", "details": str(e)}
        return {"error": "No JSON found in response"}

    def _format_feasibility(self, feasibility: dict) -> str:
        """Format feasibility result for prompt."""
        status = feasibility.get("feasibility", "UNKNOWN")
        novelty = feasibility.get("novelty_points", [])

        lines = [f"Status: {status}"]
        if novelty:
            lines.append("Novelty Points:")
            lines.extend(f"  - {n}" for n in novelty[:5])

        return "\n".join(lines)

    def _format_references(self, references: list[dict]) -> str:
        """Format references for prompt."""
        if not references:
            return "No references provided."

        lines = []
        for i, ref in enumerate(references[:15], 1):
            authors = ref.get("authors", ["Unknown"])
            if isinstance(authors, list):
                author_str = ", ".join(authors[:3])
                if len(authors) > 3:
                    author_str += ", et al."
            else:
                author_str = str(authors)

            title = ref.get("title", "Unknown")
            year = ref.get("year", "N/A")
            doi = ref.get("doi", "")

            lines.append(f"{i}. {author_str} ({year}). {title}. {doi}")

        return "\n".join(lines)

    def _format_list(self, items: list[str]) -> str:
        """Format list items."""
        if not items:
            return "None provided."
        return "\n".join(f"- {item}" for item in items[:10])
