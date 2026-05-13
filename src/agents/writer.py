"""Writer agent - document drafting."""

from typing import Any

from ..config import settings
from ..llm.adapter import BaseLLMAdapter
from .base import AgentConfig, AgentContext, AgentRole, BaseAgent

DEFAULT_WRITER_PROMPT = """You are the Writer (Academic Writing Master) of the AutoResearch Agent System.

Your objective is to draft and refine professional academic papers or patent applications strictly based on the Investigator's findings and user constraints.

Core Writing Directives:
1. Grounding (Zero Hallucination): Every claim, data point, and related work MUST be grounded in the Investigator's `feasibility.json` and `literature_review.md`. Do NOT invent experimental results; if drafting a proposal, clearly state them as "expected results".
2. Structural Integrity: Strictly adhere to the specified document structures:
   - PAPER: Abstract, Intro, Related Work, Methodology, Experiments, Results, Discussion, Conclusion, References.
   - PATENT: Field, Background, Summary, Detailed Description, Claims.
3. Tone & Style: Precise, objective, concise, and confident. Use "we demonstrate" instead of "it may suggest". Use passive voice where standard in the domain.
4. ANTI-TRUNCATION & COMPLETENESS: You must output the FULL, comprehensive document. Do NOT summarize or use placeholders like "[Insert Methodology Here]". Write every section exhaustively. Expand deeply on technical details.

Revision Protocol (When receiving Reviewer feedback):
- DO NOT rewrite the entire document from scratch unless requested.
- Address the Reviewer's `actionableDirectives` precisely.
- Maintain the high quality of sections that were not criticized.

Remember: Your output is the core product. Density of information, logical flow between paragraphs, and rigorous citation mapping are your highest priorities.
"""


class WriterAgent(BaseAgent):
    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        max_tokens: int = 16384,
    ):
        custom_prompt = settings.get_agent_system_prompt("writer")
        system_prompt = custom_prompt if custom_prompt else DEFAULT_WRITER_PROMPT
        config = AgentConfig(
            role=AgentRole.WRITER,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
        )
        super().__init__(config, llm_adapter)

    async def execute(  # type: ignore[override]
        self, context: AgentContext, investigator_data: dict
    ) -> dict[str, Any]:
        """Execute the writer's drafting task."""
        # Get research findings from shared context
        feasibility = investigator_data.get("feasibility_data", {})
        literature_review = investigator_data.get("literature_review", "")

        # Draft the document
        draft = await self._create_draft(context, feasibility, literature_review)

        return {
            "node": "drafting",
            "draft": draft,
            "version": 1,
            "raw_response": draft,  # 模型原始返回的完整初稿
        }

    async def _create_draft(
        self,
        context: AgentContext,
        feasibility: dict,
        literature_review: str,
    ) -> str:
        """Create initial document draft."""
        prompt = f"""Create a COMPLETE research paper document for:

Topic: {context.topic}
Document Type: {context.doc_type}
Domain: {context.domain}
Requirements: {context.requirements or 'None'}
Template: {context.template_path or 'Not provided'}

Research Findings:
- Feasibility: {feasibility.get('conclusion', 'N/A')}
- Literature Review:
{literature_review[:4000]}

IMPORTANT: Output the COMPLETE document in {context.doc_type} format. Write every section completely from start to finish. Do NOT truncate or use placeholders. Include all sections with full content."""

        response = await self.generate_response(prompt)
        return response.content

    async def revise(
        self, context: AgentContext, current_draft: str, feedback: dict
    ) -> dict[str, Any]:
        """Revise draft based on reviewer feedback."""
        # Include more of the draft in revision prompt
        draft_excerpt = current_draft[:8000] if len(current_draft) > 8000 else current_draft
        prompt = f"""Revise the document based on reviewer feedback. Output the COMPLETE revised document.

Original Draft:
{draft_excerpt}

Reviewer Feedback:
{feedback.get('recommendations', [])}

Issues to fix:
{feedback.get('issues', [])}

IMPORTANT: Output the COMPLETE revised document. Do NOT truncate. Fix all issues and write the full document."""

        response = await self.generate_response(prompt)

        return {
            "node": "drafting",
            "draft": response.content,
            "version": feedback.get("version", 1) + 1,
        }
