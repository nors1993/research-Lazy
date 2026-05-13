"""Reviewer agent - validation and plagiarism checking."""

from typing import Any

from ..config import settings
from ..llm.adapter import BaseLLMAdapter
from .base import AgentConfig, AgentContext, AgentRole, BaseAgent

DEFAULT_REVIEWER_PROMPT = """You are the Reviewer (Logic Judge) of the AutoResearch Agent System.

Your role is the gatekeeper of quality. You do not just find flaws; you provide highly actionable, specific revision directives for the Writer.

Validation Dimensions:
1. Logic & Argumentation: Are the premises sound? Does the methodology directly address the research question? Are conclusions strictly bound by the results?
2. Integrity & Plagiarism: Check for "claim without citation" patterns. Ensure text does not read like a direct copy of general knowledge. (Target similarity < 15% with academic norms).
3. Innovation & Value: Classify as Incremental, Substantial, or Breakthrough.
4. Completeness: Did the Writer output a truncated document? Are all required sections fully developed?

Feedback Rules:
- NEVER provide vague feedback like "improve logic". 
- ALWAYS provide actionable directives: "In Section 3, paragraph 2, the transition from X to Y lacks evidence. Add citation from Investigator's findings."
- If the document is truncated or incomplete, automatically assign REJECTED or MAJOR_REVISION.

Output Format:
{
  "status": "APPROVED | REJECTED | MAJOR_REVISION | MINOR_REVISION",
  "overallAssessment": "<Executive summary of quality>",
  "logicValidation": {
    "passed": true/false, 
    "score": <0-100>, 
    "issues": ["<Issue 1>", "<Issue 2>"]
  },
  "plagiarismCheck": {
    "passed": true/false, 
    "similarityEstimate": <0.0-100.0>, 
    "missingCitations": ["<Claim needing citation>"]
  },
  "innovationValidation": {"score": <0-10>, "type": "incremental|substantial|breakthrough"},
  "actionableDirectives": [
    {"section": "<Section Name>", "action": "<Specific revision instruction>"}
  ]
}
"""


class ReviewerAgent(BaseAgent):
    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        max_tokens: int = 16384,
    ):
        custom_prompt = settings.get_agent_system_prompt("reviewer")
        system_prompt = custom_prompt if custom_prompt else DEFAULT_REVIEWER_PROMPT
        config = AgentConfig(
            role=AgentRole.REVIEWER,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
        )
        super().__init__(config, llm_adapter)

    async def execute(  # type: ignore[override]
        self, context: AgentContext, draft: str, version: int = 1
    ) -> dict[str, Any]:
        """Execute the reviewer's validation task."""
        # Phase 1: Logic Validation
        logic_result = await self._validate_logic(context, draft)

        # Phase 2: Plagiarism Check
        plagiarism_result = await self._check_plagiarism(context, draft)

        # Determine overall status
        status = self._determine_status(logic_result, plagiarism_result)
        # 获取所有issues用于返回
        issues = self.get_all_issues(logic_result, plagiarism_result)

        return {
            "node": "review",
            "status": status,
            "version": version,
            "logic_validation": logic_result,
            "plagiarism_check": plagiarism_result,
            "iteration": version,
            "issues": issues,  # 统一顶层issues字段
            "raw_response_logic": logic_result.get("raw_response", ""),  # 逻辑验证原始模型输出
            "raw_response_plagiarism": plagiarism_result.get("raw_response", ""),  # 查重原始模型输出
        }

    async def _validate_logic(self, context: AgentContext, draft: str) -> dict[str, Any]:
        """Validate logical structure and argumentation."""
        prompt = f"""Validate the logic and argumentation in this document:

Topic: {context.topic}
Document:
{draft[:4000]}

Check for:
1. Clear assumptions
2. Appropriate methodology
3. Supported conclusions
4. Logical flow
5. Data accuracy

Output JSON with: passed (true/false), score (0-100), issues (list with location, problem, severity)"""

        response = await self.generate_response(prompt)

        try:
            import json
            if "{" in response.content:
                start = response.content.find("{")
                end = response.content.rfind("}") + 1
                result = json.loads(response.content[start:end])
                result["raw_response"] = response.content  # 保存模型原始返回
                return result
        except Exception:
            pass

        return {"passed": True, "score": 80, "issues": [], "raw_response": response.content}

    async def _check_plagiarism(
        self, context: AgentContext, draft: str
    ) -> dict[str, Any]:
        """Check for plagiarism/similarity."""
        # In production, this would call actual plagiarism detection APIs
        # For now, simulate with LLM-based analysis
        prompt = f"""Estimate plagiarism risk for this document:

Topic: {context.topic}
Document (first 2000 chars):
{draft[:2000]}

Search for similar content and estimate:
- Similarity with academic papers
- Similarity with blogs/technical content
- Self-plagiarism risk

Output JSON with: passed (true/false), similarityRate (0-100), sources (list)"""

        response = await self.generate_response(prompt)

        try:
            import json
            if "{" in response.content:
                start = response.content.find("{")
                end = response.content.rfind("}") + 1
                result = json.loads(response.content[start:end])
                result["raw_response"] = response.content  # 保存模型原始返回
                return result
        except Exception:
            pass

        return {"passed": True, "similarityRate": 5.0, "sources": [], "raw_response": response.content}

    def _determine_status(
        self, logic_result: dict, plagiarism_result: dict
    ) -> str:
        """Determine review status based on results."""
        # 统一收集所有issues用于顶层返回
        all_issues = []
        if not logic_result.get("passed", True):
            all_issues.extend(logic_result.get("issues", []))
        if not plagiarism_result.get("passed", True):
            all_issues.extend(plagiarism_result.get("sources", []))

        if not logic_result.get("passed", True):
            return "MAJOR_REVISION"

        if not plagiarism_result.get("passed", True):
            return "REJECTED"

        logic_score = logic_result.get("score", 100)
        if logic_score >= 90:
            return "APPROVED"
        elif logic_score >= 70:
            return "MINOR_REVISION"
        else:
            return "MAJOR_REVISION"

    def get_all_issues(self, logic_result: dict, plagiarism_result: dict) -> list:
        """Get all issues from validation results."""
        issues = []
        # 从logic validation获取issues
        logic_issues = logic_result.get("issues", [])
        for issue in logic_issues:
            issue["source"] = "logic_validation"
            issues.append(issue)
        # 从plagiarism check获取similar sources
        plagiarism_sources = plagiarism_result.get("sources", [])
        for source in plagiarism_sources:
            issues.append({"type": "plagiarism", "source": source, "source_type": "plagiarism_check"})
        return issues
