"""Patent writing skill - CNIPA standard invention patent drafting."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .base import BaseSkill, SkillMetadata
from .constants import AI_PATTERNS_ZH
from .docx_generator import PatentDocxGenerator

# Patent writing system prompt
PATENT_WRITING_SYSTEM_PROMPT = """You are a patent drafting expert specializing in Chinese invention patents following CNIPA standards.

Your responsibilities:
1. Conduct feasibility study for patent ideas
2. Perform deep literature research on prior art
3. Draft patent documents with Claim-First methodology
4. Validate logical consistency
5. Check for plagiarism
6. Polish and remove AI writing patterns
7. Generate final .docx document

Patent Drafting Principles (Claim-First):
1. Independent claim should cover all essential steps without unnecessary details
2. Dependent claims each add exactly one technical feature
3. Every claim term must appear and be defined in the description
4. Provide parameter ranges AND preferred values for all tunable parameters
5. Include at least 2-3 embodiments with different configurations
6. State the "要解决的技术问题" clearly identifying 2-3 specific prior-art failures
7. List 4-5 "有益效果" (beneficial effects) as measurable improvements

Document Structure (CNIPA Standard):
1. 发明名称 (Title)
2. 说明书摘要 (Abstract)
3. 权利要求书 (Claims)
4. 技术领域 (Technical Field)
5. 背景技术 (Background)
6. 发明内容 (Invention Content)
7. 具体实施方式 (Detailed Description)

Chinese Patent Formatting:
- Page: A4 (21cm x 29.7cm)
- Margins: Top/Bottom 2.5cm, Left/Right 2.0cm
- Fonts: SimSun for body, SimHei for headings
- Line spacing: 22pt
"""


@dataclass
class PatentContent:
    """Patent document content structure."""

    title: str
    technical_field: str
    background: str
    invention_content: str
    detailed_description: str
    beneficial_effects: str
    abstract: str
    claims: list[dict[str, Any]]
    references: list[dict[str, Any]]


@dataclass
class PatentWritingContext:
    """Context for patent writing workflow."""

    topic: str
    technical_field: str
    prior_art_limitations: list[str]
    technical_solution: str
    beneficial_effects: list[str]
    key_innovations: list[str]
    embodiments: list[dict[str, Any]]
    language: str = "zh-CN"
    output_dir: str | None = None


class PatentWritingSkill(BaseSkill):
    """Full patent writing workflow skill."""

    def __init__(self, metadata: SkillMetadata):
        super().__init__(metadata)
        self.system_prompt = PATENT_WRITING_SYSTEM_PROMPT
        self.llm_adapter = None  # Set when execute is called

    def set_llm_adapter(self, adapter):
        """Set the LLM adapter for generating content."""
        self.llm_adapter = adapter

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute the full patent writing workflow."""
        # Extract context
        topic = context.get("topic", "")
        language = context.get("language", "zh-CN")
        output_dir = context.get("output_dir", "")

        # Step 1: Feasibility Study
        feasibility = await self._feasibility_study(topic, language)
        if feasibility.get("feasibility") == "FAIL":
            return {
                "status": "failed",
                "reason": feasibility.get("reason", "Not feasible"),
                "feasibility": feasibility,
            }

        # Step 2: Deep Research
        research = await self._deep_research(topic, language)

        # Step 3: Draft Patent (Claim-First)
        patent_content = await self._draft_patent(topic, research, language)

        # Step 4: Logic Validation
        validation = await self._logic_validation(patent_content)

        # Step 5: Plagiarism Check
        plagiarism = await self._plagiarism_check(patent_content)

        # Step 6: Polishing
        polished = await self._polish(patent_content)

        # Step 7: Publish as .docx
        output_path = await self._publish(polished, output_dir, topic, language)

        return {
            "status": "completed",
            "feasibility": feasibility,
            "research": research,
            "patent_content": patent_content.__dict__,
            "validation": validation,
            "plagiarism": plagiarism,
            "polished": polished.__dict__,
            "output_path": output_path,
        }

    async def _feasibility_study(self, topic: str, language: str) -> dict[str, Any]:
        """Step 1: Evaluate patent feasibility."""
        prompt = f"""Analyze the following patent idea for feasibility:

Topic: {topic}

Evaluate:
1. Is this direction already widely researched?
2. Are there highly similar existing patents?
3. What are the key innovation points?
4. What is the risk of collision with existing work?

Output as JSON:
{{
    "feasibility": "PASS | FAIL",
    "novelty_points": ["point1", "point2"],
    "related_work": ["patent1", "patent2"],
    "risk_of_collision": "low | medium | high",
    "reason": "explanation if FAIL"
}}

Language: {language}"""

        response = await self._generate(prompt)
        return self._parse_json_response(response)

    async def _deep_research(self, topic: str, language: str) -> dict[str, Any]:
        """Step 2: Conduct deep literature research."""
        prompt = f"""Conduct comprehensive literature research for:

Topic: {topic}

Requirements:
1. Find at least 5 highly relevant patents/publications
2. For each, provide: title, source, publication date, key insights
3. Identify the gap this patent would fill
4. List specific limitations of prior art

Output as JSON:
{{
    "literature_review": "comprehensive review text",
    "references": [
        {{"title": "...", "source": "...", "year": YYYY, "key_insight": "..."}}
    ]
}}

Language: {language}"""

        response = await self._generate(prompt)
        return self._parse_json_response(response)

    async def _draft_patent(
        self, topic: str, research: dict[str, Any], language: str
    ) -> PatentContent:
        """Step 3: Draft patent using Claim-First methodology."""
        literature_review = research.get("literature_review", "")
        references = research.get("references", [])

        prompt = f"""Draft a complete Chinese invention patent following CNIPA standards.

Title: {topic}

Background Research:
{literature_review}

References:
{self._format_references(references)}

Generate the following sections:

1. **发明名称** (Title): Create a precise, descriptive title

2. **技术领域** (Technical Field): Define the technical domain

3. **背景技术** (Background): 
   - Paragraph 1: Importance of the task
   - Paragraph 2: Existing methods and their specific limitations
   - Paragraph 3: Why existing methods fail for this problem

4. **发明内容** (Invention Content):
   - 要解决的技术问题 (Technical Problem): 2-3 specific prior-art failures
   - 技术方案概述 (Solution Overview): Numbered steps S1-S6
   - 有益效果 (Beneficial Effects): 4-5 measurable improvements

5. **权利要求书** (Claims):
   - Claim 1 (Independent): Broad method covering all essential steps
   - Claims 2-N (Dependent): Each adds one specific feature
   - Use format: "根据权利要求X所述的方法，其特征在于，..."

6. **具体实施方式** (Detailed Description):
   - Embodiment 1: Primary configuration with full parameters
   - Embodiment 2: Alternative configuration
   - Parameter Table: All configurable parameters with ranges and preferred values

Output as JSON with all sections populated.

Language: {language}"""

        response = await self._generate(prompt)
        result = self._parse_json_response(response)

        return PatentContent(
            title=result.get("title", topic),
            technical_field=result.get("technical_field", ""),
            background=result.get("background", ""),
            invention_content=result.get("invention_content", ""),
            detailed_description=result.get("detailed_description", ""),
            beneficial_effects=result.get("beneficial_effects", ""),
            abstract=result.get("abstract", ""),
            claims=result.get("claims", []),
            references=references,
        )

    async def _logic_validation(self, patent: PatentContent) -> dict[str, Any]:
        """Step 4: Validate logical consistency and claim-evidence mapping."""
        prompt = f"""Validate the following patent for logical consistency:

Title: {patent.title}

Claims:
{self._format_claims(patent.claims)}

Description Sections:
- Technical Field: {patent.technical_field}
- Background: {patent.background[:500]}...
- Invention Content: {patent.invention_content[:500]}...
- Detailed Description: {patent.detailed_description[:500]}...

Validation Checklist:
1. Every claim term is defined in description?
2. Parameter ranges provided for all tunable parameters?
3. At least 2 embodiments with different configurations?
4. Technical problem statement identifies 2-3 prior-art failures?
5. Beneficial effects list 4-5 measurable improvements?

Output as JSON:
{{
    "status": "PASS | FAIL | NEEDS_REVISION",
    "issues": [
        {{"type": "...", "location": "...", "severity": "critical | major | minor", "description": "..."}}
    ],
    "claim_evidence_map": {{"claim_1": {{"supported": true/false}}}}
}}

Language: zh-CN"""

        response = await self._generate(prompt)
        return self._parse_json_response(response)

    async def _plagiarism_check(self, patent: PatentContent) -> dict[str, Any]:
        """Step 5: Check for plagiarism/similarity."""
        # Extract key paragraphs to check
        key_text = f"""
        Title: {patent.title}
        Abstract: {patent.abstract}
        Background: {patent.background[:1000]}
        Invention: {patent.invention_content[:1000]}
        Claims: {self._format_claims(patent.claims)}
        """

        prompt = f"""Estimate plagiarism/similarity risk for this patent:

{key_text}

Check:
1. Similarity with prior art patents
2. Common technical phrases (acceptable)
3. Unique technical expressions

Output as JSON:
{{
    "passed": true/false,
    "similarity_rate": 0.0-100.0,
    "high_similarity_regions": [],
    "recommendations": []
}}

Language: zh-CN"""

        response = await self._generate(prompt)
        return self._parse_json_response(response)

    async def _polish(self, patent: PatentContent) -> PatentContent:
        """Step 6: Remove AI patterns and polish."""
        # Remove AI patterns
        abstract = self._remove_ai_patterns(patent.abstract)
        background = self._remove_ai_patterns(patent.background)
        invention = self._remove_ai_patterns(patent.invention_content)
        detailed = self._remove_ai_patterns(patent.detailed_description)

        # Enhance technical language
        invention = await self._enhance_technical(invention, "invention content")
        detailed = await self._enhance_technical(detailed, "detailed description")

        return PatentContent(
            title=patent.title,
            technical_field=patent.technical_field,
            background=background,
            invention_content=invention,
            detailed_description=detailed,
            beneficial_effects=patent.beneficial_effects,
            abstract=abstract,
            claims=patent.claims,
            references=patent.references,
        )

    async def _publish(
        self, patent: PatentContent, output_dir: str, topic: str, language: str
    ) -> str:
        """Step 7: Generate .docx file."""
        import datetime
        from pathlib import Path

        # Generate output path
        date_str = datetime.datetime.now().strftime("%Y_%m_%d")
        safe_topic = re.sub(r"[^\w\u4e00-\u9fff\s-]", "", topic)[:30]
        filename = f"{safe_topic}_{date_str}.docx"

        if output_dir:
            output_path = Path(output_dir) / filename
        else:
            output_path = Path.cwd() / filename

        # Create docx generator
        generator = PatentDocxGenerator()

        # Generate document
        output_path = generator.create_patent(
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

    async def _generate(self, prompt: str) -> str:
        """Generate content using LLM."""
        if self.llm_adapter:
            response = await self.llm_adapter.generate(
                prompt=prompt,
                system_prompt=self.system_prompt,
                temperature=0.7,
                max_tokens=16384,
            )
            return response.content
        return ""

    def _parse_json_response(self, response: str) -> dict[str, Any]:
        """Parse JSON from LLM response."""
        import json

        if "{" in response:
            start = response.find("{")
            end = response.rfind("}") + 1
            try:
                return json.loads(response[start:end])
            except json.JSONDecodeError:
                pass
        return {}

    def _format_references(self, references: list[dict]) -> str:
        """Format references for prompt."""
        if not references:
            return "No references found."

        lines = []
        for i, ref in enumerate(references, 1):
            title = ref.get("title", "Unknown")
            source = ref.get("source", "Unknown")
            year = ref.get("year", "N/A")
            insight = ref.get("key_insight", "")
            lines.append(f"{i}. [{year}] {title} ({source}): {insight}")

        return "\n".join(lines)

    def _format_claims(self, claims: list[dict]) -> str:
        """Format claims for prompt."""
        if not claims:
            return "No claims provided."

        lines = []
        for i, claim in enumerate(claims, 1):
            is_independent = claim.get("independent", False)
            marker = "[Independent]" if is_independent else "[Dependent]"
            text = claim.get("text", "")
            lines.append(f"{i}. {marker} {text}")

        return "\n".join(lines)

    def _remove_ai_patterns(self, text: str) -> str:
        from .constants import remove_ai_patterns
        return remove_ai_patterns(text, AI_PATTERNS_ZH)

    async def _enhance_technical(self, text: str, section: str) -> str:
        """Enhance technical language in text."""
        prompt = f"""Enhance the technical language of the following {section}.

Make it more precise, formal, and technically rigorous. Remove any informal expressions.

Text:
{text}

Output the enhanced text only.

Language: zh-CN"""

        return await self._generate(prompt)
