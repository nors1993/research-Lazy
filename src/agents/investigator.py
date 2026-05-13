"""Investigator agent - research and feasibility analysis."""

from typing import Any

from ..config import settings
from ..llm.adapter import BaseLLMAdapter
from ..utils.logger import get_logger
from .base import AgentConfig, AgentContext, AgentRole, BaseAgent

logger = get_logger(__name__)


DEFAULT_INVESTIGATOR_PROMPT = """You are the Investigator (Research Strategist) of the AutoResearch Agent System.

Your core objectives are to assess research feasibility and conduct rigorous, hallucination-free literature research.

1. Feasibility Assessment Criteria:
- FAIL (Infeasible): Purely hypothetical/pseudoscientific, exhaustive existing solutions with zero gap, or trivial with no academic/commercial value.
- PASS (Feasible): Clear research question, active academic/patent landscape, realistic scope, and potential for original contribution (methodological, empirical, or application-based).

2. Deep Literature Research Rules (ZERO HALLUCINATION POLICY):
- ALL referenced literature, papers, and patents MUST BE REAL. Do not invent authors, titles, or DOIs. If you cannot find enough real data, state the actual number found and explain the scarcity.
- Quantitative Goals: Aim for ≥5 sources for PATENTS, and ≥25 for PAPERS, BUT authenticity supersedes quantity.
- Synthesis: Do not just list papers. Synthesize them into a cohesive narrative identifying the "Research Gap".

3. Literature Review Structure (Output as literature_review.md):
- Introduction & Keyword Strategy
- Background & Evolution of the Field
- Current State-of-the-Art (Categorized by methodology or approach)
- Identified Research Gaps & Opportunities
- Bibliography (with actual verifiable links or standard citation format)

4. Output JSON Format (feasibility.json):
{
  "feasibility": "PASS | FAIL",
  "innovativeness": {"score": <0-10>, "analysis": "<Brief justification>"},
  "originality": {"score": <0-10>, "analysis": "<Justification>", "references": ["<Real citation 1>", "..."]},
  "researchValue": {"score": <0-10>, "analysis": "<Justification>"},
  "riskAssessment": [{"risk": "<Specific risk>", "probability": "LOW|MEDIUM|HIGH", "mitigation": "<Action>"}],
  "searchQueriesUsed": ["<query1>", "<query2>"],
  "conclusion": "<Final verdict>"
}
"""


class InvestigatorAgent(BaseAgent):
    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        max_tokens: int = 16384,
    ):
        custom_prompt = settings.get_agent_system_prompt("investigator")
        system_prompt = custom_prompt if custom_prompt else DEFAULT_INVESTIGATOR_PROMPT
        config = AgentConfig(
            role=AgentRole.INVESTIGATOR,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
        )
        super().__init__(config, llm_adapter)

    async def execute(self, context: AgentContext) -> dict[str, Any]:
        """Execute the investigator's research task."""
        # Phase 1: Feasibility Study
        feasibility = await self._assess_feasibility(context)

        if feasibility.get("feasibility") == "FAIL":
            return {
                "node": "feasibility_study",
                "feasibility": "FAIL",
                "reason": feasibility.get("conclusion", "Low feasibility"),
                **feasibility,
            }

        # Phase 2: Deep Research
        literature_review = await self._conduct_research(context)

        return {
            "node": "deep_research",
            "feasibility": "PASS",
            "feasibility_data": feasibility,
            "literature_review": literature_review,
            "raw_response_feasibility": feasibility.get("raw_response", ""),  # 可行性研究原始模型输出
            "raw_response_research": literature_review,  # 深度研究原始模型输出
        }

    async def _assess_feasibility(self, context: AgentContext) -> dict[str, Any]:
        """Assess research feasibility."""
        prompt = f"""Assess the feasibility of this research topic:

Topic: {context.topic}
Domain: {context.domain}
Requirements: {context.requirements or 'None'}

Evaluate and output JSON with: feasibility, innovativeness, originality, researchValue, riskAssessment, conclusion"""

        response = await self.generate_response(prompt)

        try:
            import json as json_module
            if "{" in response.content:
                start = response.content.find("{")
                end = response.content.rfind("}") + 1
                result = json_module.loads(response.content[start:end])
                # 验证返回数据完整性
                if "feasibility" not in result:
                    result["feasibility"] = "PASS"  # 默认PASS，需要更保守
                result["raw_response"] = response.content  # 保存模型原始返回
                return result
        except Exception as e:
            logger.warning("feasibility_json_parse_failed", topic=context.topic[:50], error=str(e))

        # Default: 保守处理，解析失败时默认PASS但记录警告
        return {"feasibility": "PASS", "conclusion": "Feasible (fallback due to parse error)", "raw_response": response.content}

    async def _conduct_research(self, context: AgentContext) -> str:
        """Conduct deep literature research."""
        prompt = f"""Conduct a comprehensive literature review for:

Topic: {context.topic}
Domain: {context.domain}

Search for relevant papers and provide:
1. Research Background (core problem)
2. Current State (main methods/approaches)
3. Future Trends (where the field is heading)
4. Key Papers (categorized list with citations)

Format as Markdown:"""

        response = await self.generate_response(prompt)
        return response.content
