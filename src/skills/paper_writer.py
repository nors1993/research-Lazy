"""Academic paper writing skill - multi-format support."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .base import BaseSkill, SkillMetadata
from .constants import AI_PATTERNS_EN, AI_PATTERNS_ZH
from .docx_generator import PaperDocxGenerator

# Paper writing system prompt
PAPER_WRITING_SYSTEM_PROMPT = """You are an academic paper writing expert. Your responsibilities:

1. Conduct feasibility study for research ideas
2. Perform comprehensive literature review
3. Draft high-quality academic papers
4. Support multiple academic formats (IEEE, Nature, Elsevier, etc.)
5. Include proper figures with logical progression
6. Validate logical consistency
7. Check for plagiarism
8. Polish and remove AI patterns
9. Generate final .docx document

Academic Paper Standards:
- Abstract: 5-sentence formula (achievement, difficulty, method, evidence, result)
- Introduction: Problem → Current limitations → Our approach → Contributions
- Related Work: Organized by themes, not individual papers
- Methodology: Enable complete reimplementation
- Results: Support claims with tables/figures
- Conclusion: Restate contribution differently from abstract

Figure Requirements:
- Figure 1: Overview/historical data
- Figure 2: Structural comparison
- Figure 3: Quantitative comparison
- Figure 4: Process/mechanism
- Figure 5: Framework/architecture (highest quality, all English)

Data Currency Rules:
- "Current status" uses data BEFORE specified time point
- "Trends" uses future data from specified time point
- Always标注数据截止日期
"""


@dataclass
class PaperContent:
    """Paper document content structure."""

    title: str
    abstract: str
    keywords: list[str]
    sections: dict[str, str]  # introduction, related_work, methodology, etc.
    figures: list[dict[str, Any]]
    tables: list[dict[str, Any]]
    references: list[dict[str, Any]]


@dataclass
class PaperWritingContext:
    """Context for paper writing workflow."""

    topic: str
    research_question: str
    domain: str
    target_format: str  # IEEE, Nature, Elsevier, etc.
    key_concepts: list[str]
    methodology: str
    expected_results: str
    language: str = "en-US"
    page_limit: int | None = None


class PaperWritingSkill(BaseSkill):
    """Full academic paper writing workflow skill."""

    def __init__(self, metadata: SkillMetadata):
        super().__init__(metadata)
        self.system_prompt = PAPER_WRITING_SYSTEM_PROMPT
        self.llm_adapter = None

    def set_llm_adapter(self, adapter):
        """Set the LLM adapter for generating content."""
        self.llm_adapter = adapter

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute the full paper writing workflow."""
        # Extract context
        topic = context.get("topic", "")
        language = context.get("language", "en-US")
        domain = context.get("domain", "General")
        target_format = context.get("target_format", "General")
        output_dir = context.get("output_dir", "")

        # Step 1: Feasibility Study
        feasibility = await self._feasibility_study(topic, domain, language)
        if feasibility.get("feasibility") == "FAIL":
            return {
                "status": "failed",
                "reason": feasibility.get("reason", "Not feasible"),
                "feasibility": feasibility,
            }

        # Step 2: Deep Research (literature review)
        research = await self._deep_research(topic, domain, language)

        # Step 3: Draft Paper
        paper_content = await self._draft_paper(
            topic, research, domain, target_format, language
        )

        # Step 4: Logic Validation
        validation = await self._logic_validation(paper_content)

        # Step 5: Plagiarism Check
        plagiarism = await self._plagiarism_check(paper_content)

        # Step 6: Polishing
        polished = await self._polish(paper_content, language)

        # Step 7: Publish as .docx
        output_path = await self._publish(polished, output_dir, topic, language)

        return {
            "status": "completed",
            "feasibility": feasibility,
            "research": research,
            "paper_content": paper_content.__dict__,
            "validation": validation,
            "plagiarism": plagiarism,
            "polished": polished.__dict__,
            "output_path": output_path,
        }

    async def _feasibility_study(
        self, topic: str, domain: str, language: str
    ) -> dict[str, Any]:
        """Step 1: Evaluate research feasibility."""
        prompt = f"""Analyze the following research idea for feasibility:

Topic: {topic}
Domain: {domain}

Evaluate:
1. Is this direction already widely studied?
2. Are there highly similar existing papers?
3. What are the key innovation points?
4. What is the risk of collision with existing work?

Output as JSON:
{{
    "feasibility": "PASS | FAIL",
    "novelty_points": ["point1", "point2"],
    "related_work": ["paper1", "paper2"],
    "risk_of_collision": "low | medium | high",
    "reason": "explanation if FAIL"
}}

Language: {language}"""

        response = await self._generate(prompt)
        return self._parse_json_response(response)

    async def _deep_research(self, topic: str, domain: str, language: str) -> dict[str, Any]:
        """Step 2: Conduct comprehensive literature review."""
        prompt = f"""Conduct comprehensive literature research for:

Topic: {topic}
Domain: {domain}

Requirements:
1. Find at least 15 highly relevant publications
2. Each must have DOI (verify existence)
3. Include both recent and foundational papers
4. Organize by research themes
5. For each: title, authors, year, DOI, key contribution, methodology

Search Strategy:
- CrossRef API (preferred for reliability)
- Semantic Scholar (backup)
- arXiv (STEM papers only)

Output as JSON:
{{
    "literature_review": "comprehensive review organized by themes",
    "references": [
        {{
            "title": "...",
            "authors": ["..."],
            "year": YYYY,
            "doi": "10.xxxx/xxxxx",
            "journal": "...",
            "key_contribution": "...",
            "methodology": "..."
        }}
    ],
    "research_gaps": ["gap1", "gap2"],
    "methodology_options": [{{"method": "...", "pros": "...", "cons": "..."}}]
}}

Language: {language}"""

        response = await self._generate(prompt)
        return self._parse_json_response(response)

    async def _draft_paper(
        self,
        topic: str,
        research: dict[str, Any],
        domain: str,
        target_format: str,
        language: str,
    ) -> PaperContent:
        """Step 3: Draft academic paper."""
        literature_review = research.get("literature_review", "")
        references = research.get("references", [])
        research_gaps = research.get("research_gaps", [])
        methodology_options = research.get("methodology_options", [])

        prompt = f"""Draft a complete academic paper following {target_format} format.

Title: {topic}
Domain: {domain}

Literature Review:
{literature_review}

Research Gaps Identified:
{self._format_list(research_gaps)}

Methodology Options:
{self._format_methodologies(methodology_options)}

Generate the following sections with FULL content (no placeholders):

1. **Title**: Clear, specific, not overly broad

2. **Abstract** (5-sentence formula):
   - Sentence 1: What we achieved
   - Sentence 2: Why it is hard and important
   - Sentence 3: How we do it (with technical keywords)
   - Sentence 4: What evidence we have
   - Sentence 5: Our most remarkable result

3. **Keywords**: 4-6 terms, first letter capitalized

4. **Introduction**:
   - Problem statement (1-2 paragraphs)
   - Current approaches and limitations (1-2 paragraphs)
   - Our approach overview (1 paragraph)
   - Contributions list (bullet points)
   - Paper structure (1 paragraph)

5. **Related Work** (organized by themes, not papers):
   - Theme 1: [content]
   - Theme 2: [content]
   - ...

6. **Methodology** (enable reimplementation):
   - Overview (1-2 paragraphs)
   - Formal description/algorithm
   - All hyperparameters and settings
   - Implementation details

7. **Experiments/Results**:
   - Dataset descriptions
   - Evaluation metrics
   - Baselines compared
   - Results with tables/figures

8. **Discussion**:
   - Key findings
   - Implications
   - Limitations

9. **Conclusion**:
   - Restate contribution (different words from abstract)
   - Summarize key findings
   - Future work (2-3 concrete next steps)

10. **References**: Format according to {target_format} style

Output as JSON with all sections populated.

Language: {language}"""

        response = await self._generate(prompt)
        result = self._parse_json_response(response)

        return PaperContent(
            title=result.get("title", topic),
            abstract=result.get("abstract", ""),
            keywords=result.get("keywords", []),
            sections=result.get("sections", {}),
            figures=result.get("figures", []),
            tables=result.get("tables", []),
            references=references,
        )

    async def _logic_validation(self, paper: PaperContent) -> dict[str, Any]:
        """Step 4: Validate logical consistency."""
        section_items = []
        for k, v in paper.sections.items():
            if v:
                content = v if isinstance(v, str) else "\n".join(str(item) for item in v)
                section_items.append(f"## {k.upper()}\n{content[:500]}...")
        sections_text = "\n\n".join(section_items)

        prompt = f"""Validate the following paper for logical consistency:

Title: {paper.title}

Sections:
{sections_text}

Validation Checklist:
1. All claims have supporting evidence?
2. No logical contradictions between sections?
3. Consistent terminology throughout?
4. All figures/tables properly referenced?
5. Methods enable reimplementation?
6. Results support conclusions?

Output as JSON:
{{
    "status": "PASS | FAIL | NEEDS_REVISION",
    "issues": [
        {{
            "type": "claim_evidence_mismatch | logical_contradiction | terminology_inconsistency",
            "severity": "critical | major | minor",
            "location": "section.paragraph",
            "description": "...",
            "suggested_fix": "..."
        }}
    ],
    "claim_evidence_map": {{"claim_1": {{"supported": true/false, "evidence": "..."}}}},
    "statistics": {{
        "total_claims": N,
        "supported_claims": N,
        "unsupported_claims": N,
        "contradictions": N
    }}
}}

Language: en-US"""

        response = await self._generate(prompt)
        return self._parse_json_response(response)

    async def _plagiarism_check(self, paper: PaperContent) -> dict[str, Any]:
        """Step 5: Check for plagiarism/similarity."""
        # Check abstract and introduction for higher standards
        key_text = f"""
        Title: {paper.title}
        Abstract: {paper.abstract}
        Introduction: {paper.sections.get('introduction', '')[:1000]}
        """

        prompt = f"""Estimate plagiarism/similarity risk for this paper:

{key_text}

Section-specific thresholds:
- Abstract: <10% similarity acceptable
- Introduction: <20% acceptable
- Related Work: <30% acceptable (by nature discusses others' work)
- Methodology: <15% acceptable
- Results: <10% acceptable
- Conclusion: <15% acceptable

Output as JSON:
{{
    "overall_similarity": 0.0-100.0,
    "status": "pass | needs_revision | critical",
    "sections": [
        {{
            "section": "...",
            "similarity_score": 0.0-100.0,
            "issues": []
        }}
    ],
    "recommendations": ["..."]
}}

Language: en-US"""

        response = await self._generate(prompt)
        return self._parse_json_response(response)

    async def _polish(self, paper: PaperContent, language: str) -> PaperContent:
        """Step 6: Remove AI patterns and enhance writing."""
        patterns = AI_PATTERNS_ZH if language == "zh-CN" else AI_PATTERNS_EN

        # Remove AI patterns from each section
        polished_sections = {}
        for section_name, section_content in paper.sections.items():
            polished_sections[section_name] = self._remove_ai_patterns(
                section_content, patterns
            )

        # Enhance technical language
        for section_name in ["introduction", "methodology", "results"]:
            if section_name in polished_sections:
                polished_sections[section_name] = await self._enhance_section(
                    polished_sections[section_name], section_name, language
                )

        # Polish abstract
        abstract = await self._enhance_abstract(paper.abstract, language)

        return PaperContent(
            title=paper.title,
            abstract=abstract,
            keywords=paper.keywords,
            sections=polished_sections,
            figures=paper.figures,
            tables=paper.tables,
            references=paper.references,
        )

    async def _publish(
        self, paper: PaperContent, output_dir: str, topic: str, language: str
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
        generator = PaperDocxGenerator(language=language)

        # Generate document
        output_path_str = generator.create_paper(
            title=paper.title,
            abstract=paper.abstract,
            keywords=paper.keywords,
            sections=paper.sections,
            references=paper.references,
            output_path=str(output_path),
        )

        return output_path_str

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

    def _format_list(self, items: list[str]) -> str:
        """Format list items for prompt."""
        if not items:
            return "None provided."
        return "\n".join(f"- {item}" for item in items)

    def _format_methodologies(self, methods: list[dict]) -> str:
        """Format methodology options for prompt."""
        if not methods:
            return "None provided."

        lines = []
        for i, m in enumerate(methods, 1):
            method = m.get("method", "Unknown")
            pros = m.get("pros", "")
            cons = m.get("cons", "")
            lines.append(f"{i}. {method}: Pros({pros}), Cons({cons})")

        return "\n".join(lines)

    def _remove_ai_patterns(self, text: str, patterns: list[str]) -> str:
        from .constants import remove_ai_patterns
        return remove_ai_patterns(text, patterns)

    async def _enhance_section(self, text: str, section: str, language: str) -> str:
        """Enhance technical language in a section."""
        prompt = f"""Enhance the {section} section of an academic paper.

Make it more precise, formal, and academically rigorous. 
- Remove informal expressions
- Use confident, declarative statements
- Add domain-specific terminology
- Ensure logical flow

Original text:
{text[:2000]}

Output the enhanced text only.

Language: {language}"""

        return await self._generate(prompt)

    async def _enhance_abstract(self, abstract: str, language: str) -> str:
        """Enhance the abstract."""
        prompt = f"""Enhance the following abstract following the 5-sentence formula:

1. What we achieved
2. Why it is hard and important
3. How we do it (with technical keywords)
4. What evidence we have
5. Our most remarkable result

Original abstract:
{abstract}

Output the enhanced abstract only. Must have exactly 5 sentences.

Language: {language}"""

        return await self._generate(prompt)
