"""Patent Agent - specialized agent for patent writing workflow."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from ..agents.base import AgentConfig, AgentContext, AgentRole, BaseAgent
from ..llm.adapter import BaseLLMAdapter
from ..skills.constants import AI_PATTERNS_ZH
from ..skills.docx_generator import PatentDocxGenerator
from ..skills.patent_writer import PatentContent, PatentWritingSkill
from ..utils.logger import get_logger

logger = get_logger(__name__)


PATENT_AGENT_SYSTEM_PROMPT = """You are a Patent Writing Expert Agent specializing in Chinese invention patents (CNIPA standards). 
Your role is to orchestrate the workflow from raw idea to a legally robust, highly defensible .docx patent application.

Core Legal & Drafting Principles (CRITICAL):
1. The Trinity of Patentability: The document MUST establish a flawless logical chain between:
   - 要解决的技术问题 (The specific technical problem in prior art)
   - 技术方案 (The proposed technical solution)
   - 有益效果 (The measurable, technical effects/improvements)
2. Claim-First Methodology: 
   - Draft Claims BEFORE the Detailed Description.
   - Claim 1 (Independent): Must have the broadest reasonable scope. Split into preamble (前序部分) and characterizing portion (特征部分) using the phrase "其特征在于：" (characterized in that).
   - Claims 2-N (Dependent): Each adds specific, limiting technical features.
3. Strict Lexical Consistency (充分公开与支持): EVERY single noun/term used in the Claims MUST appear and be fully explained in the Detailed Description. Do not use synonyms interchangeably.
4. Parameter Ranges: Provide broad ranges, preferred ranges, and optimal values.
5. Embodiments (实施例): Provide at least 2-3 distinct embodiments proving the technical effect.

CNIPA Document Structure & Content Rules:
1. 发明名称 (Title): Concise, indicating the subject matter (e.g., "一种...的方法及系统").
2. 说明书摘要 (Abstract): Max 300 words, strictly summarizing the core technical solution and use case.
3. 权利要求书 (Claims): The legal boundary. Strict formatting required.
4. 技术领域 (Technical Field): One sentence defining the specific industry/field.
5. 背景技术 (Background): Expose 2-3 specific flaws in current technologies (Do NOT praise prior art too much).
6. 发明内容 (Invention Content): Explicitly state the Problem, Solution (copy-pasting Claims with transition words), and 4-5 measurable Effects.
7. 具体实施方式 (Detailed Description): Comprehensive blueprint enabling a person skilled in the art to implement it.

Formatting & Output Constraints:
- Provide structured text ready for .docx generation (Page: A4, Margins: 2.5cm/2.0cm, Body font: SimSun, Heading font: SimHei, Spacing: 22pt). Use standard markdown headings to denote sections.

Polishing & De-AIization Rules:
- Tone: Highly technical, objective, legalistic. 
- BAN phrases: "综上所述", "总而言之", "值得注意的是", "需要指出的是", "可以看出".
- STYLE REQUIREMENT: Avoid conversational transitions. Start sentences directly with the component or action (e.g., "所述处理器用于..." instead of "首先，所述处理器...").
"""


class PatentAgent(BaseAgent):
    """Agent specialized in patent writing."""

    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        max_tokens: int = 16384,
    ):
        config = AgentConfig(
            role=AgentRole.EDITOR,  # Using EDITOR role as base
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=PATENT_AGENT_SYSTEM_PROMPT,
        )
        super().__init__(config, llm_adapter)
        self.patent_skill = None

    def _init_patent_skill(self) -> PatentWritingSkill:
        """Initialize patent writing skill with LLM adapter."""
        from ..skills.base import SkillMetadata

        metadata = SkillMetadata(
            name="patent-writing",
            description="Write patent for any domain following CNIPA standards",
            category="research",
            tags=["patent", "CNIPA", "invention patent", "claim-first"],
        )

        skill = PatentWritingSkill(metadata)
        skill.set_llm_adapter(self.llm_adapter)
        return skill

    async def execute(self, context: AgentContext) -> dict[str, Any]:
        """Execute the patent writing workflow."""
        logger.info("patent_agent_executing", task_id=context.task_id, topic=context.topic)

        # Initialize skill
        self.patent_skill = self._init_patent_skill()

        # Prepare execution context
        exec_context = {
            "topic": context.topic,
            "language": context.language,
            "output_dir": getattr(context, "output_dir", ""),
            "requirements": context.requirements,
            "template_path": context.template_path,
            "domain": context.domain,
            "doc_type": "PATENT",
        }

        # Execute full workflow
        result = await self.patent_skill.execute(exec_context)

        return {
            "status": result.get("status", "unknown"),
            "node": "patent_writing",
            "output_path": result.get("output_path"),
            "feasibility": result.get("feasibility"),
            "research": result.get("research"),
            "patent_content": result.get("patent_content"),
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
        """Execute workflow with pre-computed results (for integration with existing system)."""
        logger.info("patent_workflow_execution", task_id=context.task_id)

        if not self.patent_skill:
            self.patent_skill = self._init_patent_skill()

        # If we have pre-computed results, use them directly
        if feasibility_result and research_result:
            # Generate patent from existing research
            patent_content = await self._draft_patent_from_research(
                context, feasibility_result, research_result
            )

            # Validation
            validation = await self._validate_logic(patent_content)

            # Plagiarism check
            plagiarism = await self._plagiarism_check(patent_content)

            # Polish
            polished = await self._polish(patent_content)

            # Publish
            output_path = await self._publish(polished, context)

            return {
                "status": "completed",
                "patent_content": patent_content.__dict__,
                "validation": validation,
                "plagiarism": plagiarism,
                "polished": polished.__dict__,
                "output_path": output_path,
            }

        # Otherwise execute full workflow
        return await self.execute(context)

    async def _draft_patent_from_research(
        self,
        context: AgentContext,
        feasibility: dict[str, Any],
        research: dict[str, Any],
    ) -> PatentContent:
        """Draft patent using pre-computed feasibility and research results."""
        from ..skills.patent_writer import PatentContent

        user_requirements = ""
        if context.requirements:
            user_requirements = f"""
User Requirements:
{context.requirements}
"""

        template_section = ""
        if context.template_content:
            template_section = f"""
Patent Template Structure (must follow):
{context.template_content}
"""

        prompt = f"""Draft a complete Chinese invention patent following CNIPA standards.

Topic: {context.topic}
Domain: {context.domain}
{user_requirements}{template_section}
Feasibility Study:
{self._format_feasibility(feasibility)}

Literature Review:
{research.get('literature_review', '')[:3000]}

References:
{self._format_references(research.get('references', []))}

Generate all sections of the patent document.

Output as JSON with the following structure:
{{
    "title": "发明名称",
    "technical_field": "技术领域描述",
    "background": "背景技术（4段结构）",
    "invention_content": "发明内容",
    "beneficial_effects": "有益效果",
    "detailed_description": "具体实施方式",
    "abstract": "说明书摘要",
    "claims": [
        {{"text": "独立权利要求1内容", "independent": true}},
        {{"text": "从属权利要求2内容", "independent": false}},
        ...
    ]
}}

Language: zh-CN
Important: Output valid JSON only, no markdown code blocks."""

        response = await self.generate_response(prompt)
        result = self._parse_json_response(response.content)

        return PatentContent(
            title=result.get("title", context.topic),
            technical_field=result.get("technical_field", ""),
            background=result.get("background", ""),
            invention_content=result.get("invention_content", ""),
            detailed_description=result.get("detailed_description", ""),
            beneficial_effects=result.get("beneficial_effects", ""),
            abstract=result.get("abstract", ""),
            claims=result.get("claims", []),
            references=research.get("references", []),
        )

    async def _validate_logic(self, patent: PatentContent) -> dict[str, Any]:
        """Validate patent logic and claim-evidence mapping."""
        prompt = f"""Validate the following patent for logical consistency:

Title: {patent.title}

Claims:
{self._format_claims(patent.claims)}

Description:
Technical Field: {patent.technical_field}
Background: {patent.background[:500]}...
Invention Content: {patent.invention_content[:500]}...
Detailed Description: {patent.detailed_description[:500]}...

Validation Checklist:
1. Every claim term is defined in description?
2. Parameter ranges provided for all tunable parameters?
3. At least 2 embodiments with different configurations?
4. Technical problem identifies 2-3 prior-art failures?
5. Beneficial effects list 4-5 measurable improvements?

Output as JSON:
{{
    "status": "PASS | FAIL | NEEDS_REVISION",
    "issues": [
        {{"type": "...", "severity": "critical | major | minor", "description": "..."}}
    ]
}}

Language: zh-CN"""

        response = await self.generate_response(prompt)
        return self._parse_json_response(response.content)

    async def _plagiarism_check(self, patent: PatentContent) -> dict[str, Any]:
        """Check for plagiarism."""
        key_text = f"""
        Title: {patent.title}
        Abstract: {patent.abstract[:500]}
        Background: {patent.background[:500]}
        Invention: {patent.invention_content[:500]}
        Claims: {self._format_claims(patent.claims[:3])}
        """

        prompt = f"""Estimate plagiarism risk for this patent:

{key_text}

Output as JSON:
{{
    "passed": true/false,
    "similarity_rate": 0.0-100.0,
    "high_similarity_regions": [],
    "recommendations": []
}}

Language: zh-CN"""

        response = await self.generate_response(prompt)
        return self._parse_json_response(response.content)

    async def _polish(self, patent: PatentContent) -> PatentContent:
        from ..skills.constants import remove_ai_patterns

        def clean(text):
            return remove_ai_patterns(text, AI_PATTERNS_ZH)

        return PatentContent(
            title=clean(patent.title),
            technical_field=clean(patent.technical_field),
            background=clean(patent.background),
            invention_content=clean(patent.invention_content),
            detailed_description=clean(patent.detailed_description),
            beneficial_effects=clean(patent.beneficial_effects),
            abstract=clean(patent.abstract),
            claims=patent.claims,
            references=patent.references,
        )

    async def _publish(self, patent: PatentContent, context: AgentContext) -> str:
        """Publish patent as .docx."""
        from pathlib import Path

        # Generate output path
        date_str = datetime.now().strftime("%Y_%m_%d")
        safe_topic = re.sub(r"[^\w\u4e00-\u9fff\s-]", "", context.topic)[:30]
        filename = f"{safe_topic}_{date_str}_专利.docx"

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
        generator = PatentDocxGenerator()
        generator.create_patent(
            title=patent.title,
            abstract=patent.abstract,
            claims=patent.claims,
            technical_field=patent.technical_field,
            background=patent.background,
            invention_content=patent.invention_content,
            detailed_description=patent.detailed_description,
            beneficial_effects=patent.beneficial_effects,
            output_path=str(output_path),
        )

        return str(output_path)

    # Helper methods

    def _parse_json_response(self, response: str) -> dict[str, Any]:
        """Parse JSON from LLM response."""
        import json

        # Remove markdown code blocks if present
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
        related = feasibility.get("related_work", [])

        lines = [f"Status: {status}"]
        if novelty:
            lines.append("Novelty Points:")
            lines.extend(f"  - {n}" for n in novelty)
        if related:
            lines.append("Related Work:")
            lines.extend(f"  - {r}" for r in related)

        return "\n".join(lines)

    def _format_references(self, references: list[dict]) -> str:
        """Format references for prompt."""
        if not references:
            return "No references provided."

        lines = []
        for i, ref in enumerate(references[:10], 1):
            title = ref.get("title", "Unknown")
            source = ref.get("source", "Unknown")
            year = ref.get("year", "N/A")
            lines.append(f"{i}. [{year}] {title} ({source})")

        return "\n".join(lines)

    def _format_claims(self, claims: list[dict]) -> str:
        """Format claims for prompt."""
        if not claims:
            return "No claims provided."

        lines = []
        for i, claim in enumerate(claims[:10], 1):
            is_ind = claim.get("independent", False)
            marker = "[Independent]" if is_ind else "[Dependent]"
            lines.append(f"{i}. {marker} {claim.get('text', '')}")

        return "\n".join(lines)
