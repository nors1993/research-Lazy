"""Editor orchestrator agent - main coordinator."""

from typing import Any

from ..config import settings
from ..llm.adapter import BaseLLMAdapter
from ..utils.logger import get_logger
from .base import AgentConfig, AgentContext, AgentRole, BaseAgent
from .investigator import InvestigatorAgent
from .reviewer import ReviewerAgent
from .writer import WriterAgent

logger = get_logger(__name__)


DEFAULT_EDITOR_PROMPT = """You are the Editor (Chief Orchestrator) of the AutoResearch Agent System.

Your role is the central brain of the system:
1. Parse user intent precisely (extract domain, docType, tone, and specific constraints).
2. Delegate tasks strictly to sub-agents (Investigator, Writer, Reviewer) providing clear context.
3. Monitor execution state and manage workflow transitions.
4. Make strategic decisions (Continue, Retry, Early Exit) based on sub-agent outputs.
5. Perform final polishing (De-AIization) and safe publishing.

Delegation & Data Flow Rules:
- To Investigator: Send intent, domain, docType, and specific knowledge gaps to fill.
- To Writer: Send approved feasibility JSON, literature review, and user templates.
- To Reviewer: Send drafted document PLUS the original user requirements to ensure alignment.

Strict Decision Logic:
- [EARLY_EXIT]: If Investigator returns feasibility = FAIL, terminate immediately with a clear explanation to the user.
- [RETRY]: If Reviewer returns MAJOR_REVISION, send specific feedback back to the Writer. Maximum 3 retries.
- [APPROVE]: If Reviewer returns APPROVED or MINOR_REVISION (and handled), proceed to final polishing.

Node 7: Polishing & De-AIization (CRITICAL):
Transform typical LLM-sounding text into authentic, expert-level academic/patent writing.
- BAN LIST (Do not use): "综上所述", "总而言之", "值得注意的是", "需要指出的是", "Delve into", "Tapestry", "Crucial", "Vital", "It goes without saying", "In summary".
- REPLACE: "本文/本研究..." -> Action-oriented subject openings (e.g., "Our methodology introduces...").
- ENFORCE: Use precise data points instead of vague qualifiers (e.g., replace "excellent performance" with actual metric numbers).
- TONE: Authoritative, objective, concise, and heavily utilizing domain-specific nomenclature.

Node 8: Publishing & Safe Cleanup:
- Generate the final formatted document and move to the designated output directory.
- SAFE CLEANUP: ONLY remove explicitly generated temporary files (*.py, *.mjs, *.js, *.ts) inside the specific task's temporary workspace. NEVER touch system or core project files.
- Notify the user with the final absolute path.
"""


class EditorAgent(BaseAgent):
    def __init__(
        self,
        llm_adapter: BaseLLMAdapter,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        max_tokens: int = 16384,
    ):
        custom_prompt = settings.get_agent_system_prompt("editor")
        system_prompt = custom_prompt if custom_prompt else DEFAULT_EDITOR_PROMPT
        config = AgentConfig(
            role=AgentRole.EDITOR,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
        )
        super().__init__(config, llm_adapter)
        self._current_context: AgentContext | None = None

    async def generate_response(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ):
        effective_system = self.config.system_prompt

        if self._current_context:
            # temp_prompt 优先级最高
            if self._current_context.temp_prompt:
                effective_system = (
                    f"{self._current_context.temp_prompt}\n\n---\n\n{effective_system}"
                )
            # 附件内容
            if self._current_context.attachment_content:
                attachment_intro = (
                    f"【附件内容】\n{self._current_context.attachment_content}\n\n---\n\n"
                )
                effective_system = f"{attachment_intro}{effective_system}"
            # 模板内容（文档结构参考）
            if self._current_context.template_content:
                template_intro = (
                    f"【文档模板结构参考】\n{self._current_context.template_content}\n\n---\n\n"
                )
                effective_system = f"{template_intro}{effective_system}"

        if system_prompt:
            effective_system = f"{effective_system}\n\n{system_prompt}"

        return await self.llm_adapter.generate(
            prompt=prompt,
            system_prompt=effective_system,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

    async def execute(self, context: AgentContext) -> dict[str, Any]:
        """Execute the editor's orchestration logic."""
        logger.info("editor_executing", task_id=context.task_id, topic=context.topic)

        # Step 1: Intent Analysis
        intent_result = await self._analyze_intent(context)

        # Store domain and doc_type in shared data
        context.shared_data["domain"] = intent_result.get("domain", context.domain)
        context.shared_data["doc_type"] = intent_result.get("doc_type", context.doc_type)

        return {
            "status": "intent_analyzed",
            "domain": context.shared_data["domain"],
            "doc_type": context.shared_data["doc_type"],
            "next_node": "feasibility_study",
        }

    async def _analyze_intent(self, context: AgentContext) -> dict[str, Any]:
        """Analyze user intent to extract domain and doc type."""
        prompt = f"""Analyze the following research topic and extract the domain and document type.

Topic: {context.topic}
Requirements: {context.requirements or "None"}
Template: {context.template_path or "None"}

Output as JSON with keys: domain, doc_type, confidence (0-1)"""

        response = await self.generate_response(prompt)

        # Parse response (in production, use structured output)
        try:
            import json as json_module

            # Try to extract JSON from response
            if "{" in response.content:
                start = response.content.find("{")
                end = response.content.rfind("}") + 1
                json_str = response.content[start:end]
                result = json_module.loads(json_str)
                # 验证返回数据完整性
                if not result.get("domain"):
                    result["domain"] = context.domain
                if not result.get("doc_type"):
                    result["doc_type"] = context.doc_type
                result["raw_response"] = response.content  # 保存模型原始返回
                return result
        except Exception as e:
            logger.warning("intent_json_parse_failed", task_id=context.task_id, error=str(e))

        # Default fallback - 使用较低confidence表示不确定性
        return {
            "domain": context.domain,
            "doc_type": context.doc_type,
            "confidence": 0.5,  # 降低默认confidence，表示解析失败的不确定性
            "raw_response": response.content,  # 模型原始返回信息
        }

    async def coordinate_workflow(
        self,
        context: AgentContext,
        current_node: str,
        node_result: dict[str, Any],
    ) -> dict[str, Any]:
        """Coordinate workflow based on node results."""
        logger.info(
            "editor_coordinating",
            task_id=context.task_id,
            current_node=current_node,
        )

        # Decision logic based on node results
        if current_node == "feasibility_study":
            if node_result.get("feasibility") == "FAIL":
                return {
                    "action": "early_exit",
                    "reason": node_result.get("reason", "Infeasible research topic"),
                }
            return {"action": "proceed", "next_node": "deep_research"}

        if current_node == "logic_validation" or current_node == "plagiarism_check":
            review_status = node_result.get("status")
            if review_status == "APPROVED":
                return {"action": "proceed", "next_node": "polishing"}
            elif review_status == "REJECTED":
                return {"action": "terminate", "reason": "Rejected by reviewer"}
            elif review_status == "MAJOR_REVISION":
                iteration = node_result.get("iteration", 0)
                if iteration < 3:
                    return {"action": "retry", "next_node": "drafting"}
                else:
                    return {"action": "terminate", "reason": "Max iterations reached"}

        if current_node == "polishing":
            return {"action": "proceed", "next_node": "publishing"}

        if current_node == "publishing":
            return {"action": "complete", "output_path": node_result.get("output_path")}

        return {"action": "proceed", "next_node": "deep_research"}

    async def perform_polishing(self, context: AgentContext, draft: str) -> dict[str, Any]:
        """Perform the exclusive polishing task."""
        prompt = f"""You are performing the final polishing (de-AIization) of a research document.

Apply these transformations:
1. Remove: "综上所述", "总而言之", "值得注意的是", "需要指出的是", "本文/本研究中"
2. Replace generic claims with specific data
3. Use confident, expert-level language
4. Add domain-specific terminology

Original draft:
{draft}

Output the polished document:"""

        response = await self.generate_response(prompt)

        return {
            "status": "polished",
            "polished_content": response.content,
            "raw_response": response.content,  # 模型原始返回内容
        }

    async def perform_publishing(self, context: AgentContext, final_content: str) -> dict[str, Any]:
        """Perform the exclusive publishing task."""
        import re
        from datetime import datetime

        from ..utils.workspace import workspace_manager

        # Initialize workspace
        workspace_manager.initialize()

        # Create task workspace with subdirectories
        workspace_manager.create_task_workspace(context.task_id)

        # Generate filename from topic and date
        # Topic: "深度学习在医疗影像诊断中的应用" -> "深度学习在医疗影像诊断中的应用_2026_05_10.md"
        date_str = datetime.now().strftime("%Y_%m_%d")
        # Sanitize topic for filename (remove special chars)
        safe_topic = re.sub(r"[^\w\u4e00-\u9fff\s-]", "", context.topic)
        safe_topic = safe_topic.strip()[:50]  # Limit length
        final_filename = f"{safe_topic}_{date_str}.md"

        # Write final content to temp workspace first
        workspace_manager.save_file(
            task_id=context.task_id, filename="final.md", content=final_content
        )

        # Move to output directory with proper naming
        # Use doc_type as prefix for directory
        doc_type_prefix = context.doc_type.lower() if context.doc_type else "paper"
        output_path = workspace_manager.move_to_output(
            task_id=context.task_id,
            filename="final.md",
            final_filename=final_filename,
            output_dir_prefix=doc_type_prefix,
        )

        # Cleanup temp files (but keep output)
        workspace_manager.cleanup_temp_files(context.task_id)

        return {
            "status": "published",
            "output_path": str(output_path),
            "message": "Document published successfully",
        }

    async def execute_workflow(
        self,
        context: AgentContext,
        investigator_adapter=None,
        writer_adapter=None,
        reviewer_adapter=None,
    ) -> dict[str, Any]:
        """Execute the full 8-step workflow.

        Args:
            context: The agent context
            investigator_adapter: Optional LLM adapter for investigator agent
            writer_adapter: Optional LLM adapter for writer agent
            reviewer_adapter: Optional LLM adapter for reviewer agent
        """
        self._current_context = context
        logger.info("workflow_execution_started", task_id=context.task_id)

        try:
            doc_type = (
                context.doc_type.strip().upper()
                if context.doc_type and context.doc_type.strip()
                else "PAPER"
            )
            if doc_type == "PATENT":
                result = await self._execute_patent_workflow(
                    context, investigator_adapter, writer_adapter, reviewer_adapter
                )
            elif doc_type == "PAPER":
                result = await self._execute_paper_workflow(
                    context, investigator_adapter, writer_adapter, reviewer_adapter
                )
            else:
                result = await self._execute_standard_workflow(
                    context, investigator_adapter, writer_adapter, reviewer_adapter
                )
        finally:
            if self._current_context:
                self._current_context.temp_prompt = None
                self._current_context.attachment_content = None
                self._current_context.template_content = None
            self._current_context = None

        return result

    async def _execute_patent_workflow(
        self,
        context: AgentContext,
        investigator_adapter=None,
        writer_adapter=None,
        reviewer_adapter=None,
    ) -> dict[str, Any]:
        """Execute the patent-specific workflow: feasibility → research → drafting → validation → publishing."""
        import uuid

        from ..api.event_storage import _task_status, publish_step_event, update_task_status
        from ..api.events import event_publisher
        from ..workflow.nodes.extended import EXTENDED_NODES

        task_uuid = None
        try:
            if context.task_id:
                try:
                    task_uuid = uuid.UUID(context.task_id)
                except ValueError:
                    logger.warning(
                        "Invalid task_id format, cannot convert to UUID", task_id=context.task_id
                    )
                else:
                    await event_publisher.publish_node_start(
                        task_uuid, "patent_feasibility", f"开始专利可行性分析: {context.topic}"
                    )
                    publish_step_event(
                        task_uuid,
                        "node_start",
                        "patent_feasibility",
                        f"开始专利可行性分析: {context.topic}",
                    )
        except Exception as e:
            logger.warning(
                "Failed to publish initial events", task_id=context.task_id, error=str(e)
            )

        inv_adapter = investigator_adapter or self.llm_adapter

        workflow_results = {
            "steps_completed": [],
            "outputs": {},
        }

        def _update_current_node(node_name: str):
            if task_uuid and task_uuid in _task_status:
                _task_status[task_uuid]["current_node"] = node_name

        async def _publish_node_start(node: str, message: str, detail: str = ""):
            try:
                if task_uuid:
                    _update_current_node(node)
                    await event_publisher.publish_node_start(task_uuid, node, message)
                    publish_step_event(
                        task_uuid, "node_start", node, message, detail if detail else ""
                    )
            except Exception as e:
                logger.warning(f"Failed to publish node_start for {node}", error=str(e))

        async def _publish_node_complete(node: str, message: str, detail: str = ""):
            try:
                if task_uuid:
                    await event_publisher.publish_node_complete(task_uuid, node, message)
                    publish_step_event(
                        task_uuid, "node_complete", node, message, detail if detail else ""
                    )
            except Exception as e:
                logger.warning(f"Failed to publish node_complete for {node}", error=str(e))

        try:
            # Step 1: Patent Feasibility
            feas_node_cls = EXTENDED_NODES["patent_feasibility"]
            feas_node = feas_node_cls(inv_adapter)
            result = await feas_node.execute(context)
            workflow_results["steps_completed"].append("patent_feasibility")
            workflow_results["outputs"]["feasibility"] = result.output

            feas_output = result.output or {}
            feas_status = feas_output.get("feasibility", "UNKNOWN")
            feas_detail = str(feas_output)
            await _publish_node_complete(
                "patent_feasibility", f"专利可行性: {feas_status}", feas_detail
            )

            # Early exit if not feasible
            if feas_status and feas_status.upper().strip() == "FAIL":
                if task_uuid:
                    update_task_status(
                        task_uuid, "FAILED", error_message=feas_output.get("reason", "不可行")
                    )
                return {
                    "status": "failed",
                    "reason": feas_output.get("reason", "不可行"),
                    "results": workflow_results,
                }

            # Step 2: Patent Research
            research_node_cls = EXTENDED_NODES["patent_research"]
            research_node = research_node_cls(inv_adapter)
            context.shared_data["patent_feasibility"] = feas_output

            await _publish_node_start(
                "patent_research", "正在进行专利文献研究...", "正在搜索和整理专利文献..."
            )
            result = await research_node.execute(context)
            workflow_results["steps_completed"].append("patent_research")
            workflow_results["outputs"]["research"] = result.output

            research_output = result.output or {}
            research_detail = str(research_output)
            await _publish_node_complete("patent_research", "专利文献研究完成", research_detail)

            context.shared_data["patent_research"] = research_output

            # Step 3: Patent Drafting
            drafting_node_cls = EXTENDED_NODES["patent_drafting"]
            drafting_node = drafting_node_cls(inv_adapter)

            await _publish_node_start(
                "patent_drafting", "正在撰写专利申请文档...", "正在生成专利权利要求书和说明书..."
            )
            result = await drafting_node.execute(context)
            workflow_results["steps_completed"].append("patent_drafting")
            workflow_results["outputs"]["drafting"] = result.output

            drafting_output = result.output or {}
            drafting_detail = str(drafting_output)
            await _publish_node_complete("patent_drafting", "专利申请文档撰写完成", drafting_detail)

            context.shared_data["patent_drafting"] = drafting_output

            # Step 4: Patent Validation
            validation_node_cls = EXTENDED_NODES["patent_validation"]
            validation_node = validation_node_cls(inv_adapter)

            await _publish_node_start(
                "patent_validation", "正在进行专利逻辑验证...", "正在验证权利要求书的逻辑一致性..."
            )
            result = await validation_node.execute(context)
            workflow_results["steps_completed"].append("patent_validation")
            workflow_results["outputs"]["validation"] = result.output

            validation_output = result.output or {}
            validation_detail = str(validation_output)
            validation_status = validation_output.get("status", "N/A")
            await _publish_node_complete(
                "patent_validation", f"专利验证完成: {validation_status}", validation_detail
            )

            if validation_status and validation_status.upper().strip() == "FAIL":
                if task_uuid:
                    update_task_status(
                        task_uuid,
                        "FAILED",
                        error_message=validation_output.get("reason", "验证失败"),
                    )
                return {
                    "status": "failed",
                    "reason": validation_output.get("reason", "验证失败"),
                    "results": workflow_results,
                }

            # Step 5: Patent Publishing
            publishing_node_cls = EXTENDED_NODES["patent_publishing"]
            publishing_node = publishing_node_cls(inv_adapter)

            await _publish_node_start(
                "patent_publishing", "正在生成专利文档并发布...", "正在生成.docx格式专利文档..."
            )
            result = await publishing_node.execute(context)
            workflow_results["steps_completed"].append("patent_publishing")
            workflow_results["outputs"]["publish"] = result.output

            publishing_output = result.output or {}
            output_path = publishing_output.get("output_path", "")
            await _publish_node_complete(
                "patent_publishing", f"专利文档已发布: {output_path}", output_path
            )

            if task_uuid:
                update_task_status(task_uuid, "COMPLETED", output_path)
                _update_current_node("patent_publishing")

            logger.info("patent_workflow_completed", task_id=context.task_id)
            return {"status": "completed", "results": workflow_results}

        except Exception as e:
            try:
                if task_uuid:
                    update_task_status(task_uuid, "FAILED", error_message=str(e))
            except Exception:
                pass
            logger.exception("patent_workflow_error", task_id=context.task_id)
            return {"status": "failed", "error": str(e), "results": workflow_results}

    async def _execute_paper_workflow(
        self,
        context: AgentContext,
        investigator_adapter=None,
        writer_adapter=None,
        reviewer_adapter=None,
    ) -> dict[str, Any]:
        """Execute the paper-specific workflow: feasibility → research → drafting → publishing."""
        import uuid

        from ..api.event_storage import _task_status, publish_step_event, update_task_status
        from ..api.events import event_publisher
        from ..workflow.nodes.extended import EXTENDED_NODES

        task_uuid = None
        try:
            if context.task_id:
                try:
                    task_uuid = uuid.UUID(context.task_id)
                except ValueError:
                    logger.warning(
                        "Invalid task_id format, cannot convert to UUID", task_id=context.task_id
                    )
                else:
                    await event_publisher.publish_node_start(
                        task_uuid, "paper_feasibility", f"开始论文可行性分析: {context.topic}"
                    )
                    publish_step_event(
                        task_uuid,
                        "node_start",
                        "paper_feasibility",
                        f"开始论文可行性分析: {context.topic}",
                    )
        except Exception as e:
            logger.warning(
                "Failed to publish initial events", task_id=context.task_id, error=str(e)
            )

        inv_adapter = investigator_adapter or self.llm_adapter

        workflow_results = {
            "steps_completed": [],
            "outputs": {},
        }

        def _update_current_node(node_name: str):
            if task_uuid and task_uuid in _task_status:
                _task_status[task_uuid]["current_node"] = node_name

        async def _publish_node_start(node: str, message: str, detail: str = ""):
            try:
                if task_uuid:
                    _update_current_node(node)
                    await event_publisher.publish_node_start(task_uuid, node, message)
                    publish_step_event(
                        task_uuid, "node_start", node, message, detail if detail else ""
                    )
            except Exception as e:
                logger.warning(f"Failed to publish node_start for {node}", error=str(e))

        async def _publish_node_complete(node: str, message: str, detail: str = ""):
            try:
                if task_uuid:
                    await event_publisher.publish_node_complete(task_uuid, node, message)
                    publish_step_event(
                        task_uuid, "node_complete", node, message, detail if detail else ""
                    )
            except Exception as e:
                logger.warning(f"Failed to publish node_complete for {node}", error=str(e))

        try:
            # Step 1: Paper Feasibility
            feas_node_cls = EXTENDED_NODES["paper_feasibility"]
            feas_node = feas_node_cls(inv_adapter)
            result = await feas_node.execute(context)
            workflow_results["steps_completed"].append("paper_feasibility")
            workflow_results["outputs"]["feasibility"] = result.output

            feas_output = result.output or {}
            feas_status = feas_output.get("feasibility", "UNKNOWN")
            feas_detail = str(feas_output)
            await _publish_node_complete(
                "paper_feasibility", f"论文可行性: {feas_status}", feas_detail
            )

            if feas_status and feas_status.upper().strip() == "FAIL":
                if task_uuid:
                    update_task_status(
                        task_uuid, "FAILED", error_message=feas_output.get("reason", "不可行")
                    )
                return {
                    "status": "failed",
                    "reason": feas_output.get("reason", "不可行"),
                    "results": workflow_results,
                }

            # Step 2: Paper Research
            research_node_cls = EXTENDED_NODES["paper_research"]
            research_node = research_node_cls(inv_adapter)
            context.shared_data["paper_feasibility"] = feas_output

            await _publish_node_start(
                "paper_research", "正在进行学术文献研究...", "正在搜索和整理学术文献..."
            )
            result = await research_node.execute(context)
            workflow_results["steps_completed"].append("paper_research")
            workflow_results["outputs"]["research"] = result.output

            research_output = result.output or {}
            research_detail = str(research_output)
            await _publish_node_complete("paper_research", "学术文献研究完成", research_detail)

            context.shared_data["paper_research"] = research_output

            # Step 3: Paper Drafting
            drafting_node_cls = EXTENDED_NODES["paper_drafting"]
            drafting_node = drafting_node_cls(inv_adapter)

            await _publish_node_start(
                "paper_drafting", "正在撰写学术论文...", "正在生成论文正文部分..."
            )
            result = await drafting_node.execute(context)
            workflow_results["steps_completed"].append("paper_drafting")
            workflow_results["outputs"]["drafting"] = result.output

            drafting_output = result.output or {}
            drafting_detail = str(drafting_output)
            await _publish_node_complete("paper_drafting", "学术论文撰写完成", drafting_detail)

            context.shared_data["paper_drafting"] = drafting_output

            # Step 4: Paper Validation
            validation_node_cls = EXTENDED_NODES["paper_validation"]
            validation_node = validation_node_cls(inv_adapter)

            await _publish_node_start(
                "paper_validation", "正在进行论文逻辑验证...", "正在验证论文逻辑、查重和创新性..."
            )
            result = await validation_node.execute(context)
            workflow_results["steps_completed"].append("paper_validation")
            workflow_results["outputs"]["validation"] = result.output

            validation_output = result.output or {}
            validation_detail = str(validation_output)
            validation_status = validation_output.get("status", "N/A")
            await _publish_node_complete(
                "paper_validation", f"论文验证完成: {validation_status}", validation_detail
            )

            if validation_status and validation_status.upper().strip() == "FAIL":
                if task_uuid:
                    update_task_status(
                        task_uuid, "FAILED", error_message=validation_output.get("reason", "验证失败")
                    )
                return {
                    "status": "failed",
                    "reason": validation_output.get("reason", "验证失败"),
                    "results": workflow_results,
                }

            context.shared_data["paper_validation"] = validation_output

            # Step 5: Paper Publishing
            publishing_node_cls = EXTENDED_NODES["paper_publishing"]
            publishing_node = publishing_node_cls(inv_adapter)

            await _publish_node_start(
                "paper_publishing", "正在生成论文文档并发布...", "正在生成.docx格式论文文档..."
            )
            result = await publishing_node.execute(context)
            workflow_results["steps_completed"].append("paper_publishing")
            workflow_results["outputs"]["publish"] = result.output

            publishing_output = result.output or {}
            output_path = publishing_output.get("output_path", "")
            await _publish_node_complete(
                "paper_publishing", f"论文文档已发布: {output_path}", output_path
            )

            if task_uuid:
                update_task_status(task_uuid, "COMPLETED", output_path)
                _update_current_node("paper_publishing")

            logger.info("paper_workflow_completed", task_id=context.task_id)
            return {"status": "completed", "results": workflow_results}

        except Exception as e:
            try:
                if task_uuid:
                    update_task_status(task_uuid, "FAILED", error_message=str(e))
            except Exception:
                pass
            logger.exception("paper_workflow_error", task_id=context.task_id)
            return {"status": "failed", "error": str(e), "results": workflow_results}

    async def _execute_standard_workflow(
        self,
        context: AgentContext,
        investigator_adapter=None,
        writer_adapter=None,
        reviewer_adapter=None,
    ) -> dict[str, Any]:
        """Execute the original 8-step standard workflow.

        Args:
            context: The agent context
            investigator_adapter: Optional LLM adapter for investigator agent
            writer_adapter: Optional LLM adapter for writer agent
            reviewer_adapter: Optional LLM adapter for reviewer agent
        """
        import uuid

        from ..api.event_storage import _task_status, publish_step_event, update_task_status
        from ..api.events import event_publisher

        # Use provided adapters or fallback to editor's adapter
        inv_adapter = investigator_adapter or self.llm_adapter
        wri_adapter = writer_adapter or self.llm_adapter
        rev_adapter = reviewer_adapter or self.llm_adapter

        # Get agent configs from settings
        from ..config import settings

        inv_config = settings.get_agent_config("investigator")
        wri_config = settings.get_agent_config("writer")
        rev_config = settings.get_agent_config("reviewer")

        # Initialize sub-agents with their respective adapters and configs
        investigator = InvestigatorAgent(
            inv_adapter,
            model=inv_config.model,
            temperature=inv_config.temperature,
            max_tokens=inv_config.max_tokens,
        )
        writer = WriterAgent(
            wri_adapter,
            model=wri_config.model,
            temperature=wri_config.temperature,
            max_tokens=wri_config.max_tokens,
        )
        reviewer = ReviewerAgent(
            rev_adapter,
            model=rev_config.model,
            temperature=rev_config.temperature,
            max_tokens=rev_config.max_tokens,
        )

        workflow_results = {
            "steps_completed": [],
            "outputs": {},
        }

        # Convert task_id to UUID for event publishing
        task_uuid = None
        try:
            if context.task_id:
                try:
                    task_uuid = uuid.UUID(context.task_id)
                except ValueError:
                    logger.warning(
                        "Invalid task_id format, cannot convert to UUID", task_id=context.task_id
                    )
                else:
                    # Publish workflow start event
                    await event_publisher.publish_node_start(
                        task_uuid, "intent_analysis", f"开始研究: {context.topic}"
                    )
                    publish_step_event(
                        task_uuid, "node_start", "intent_analysis", f"开始研究: {context.topic}"
                    )
        except Exception as e:
            logger.warning(
                "Failed to publish initial events", task_id=context.task_id, error=str(e)
            )

        # === Helper methods for publishing node events ===
        def _update_current_node(node_name: str):
            """更新当前节点（用于API轮询）"""
            if task_uuid and task_uuid in _task_status:
                _task_status[task_uuid]["current_node"] = node_name

        async def _publish_node_start(node: str, message: str, detail: str = ""):
            """发布节点开始事件"""
            try:
                if task_uuid:
                    _update_current_node(node)
                    await event_publisher.publish_node_start(task_uuid, node, message)
                    # Pass empty string if detail is empty, not None
                    publish_step_event(
                        task_uuid, "node_start", node, message, detail if detail else ""
                    )
            except Exception as e:
                logger.warning(f"Failed to publish node_start for {node}", error=str(e))

        async def _publish_node_complete(node: str, message: str, detail: str = ""):
            """发布节点完成事件"""
            try:
                if task_uuid:
                    await event_publisher.publish_node_complete(task_uuid, node, message)
                    # Pass empty string if detail is empty, not None
                    publish_step_event(
                        task_uuid, "node_complete", node, message, detail if detail else ""
                    )
            except Exception as e:
                logger.warning(f"Failed to publish node_complete for {node}", error=str(e))

        try:
            # Step 1: Intent Analysis
            logger.info("step_intent_analysis", task_id=context.task_id)
            intent_result = await self.execute(context)
            workflow_results["steps_completed"].append("intent_analysis")
            workflow_results["outputs"]["intent"] = intent_result

            # Publish node events - 显示模型返回的完整原始信息
            intent_detail = intent_result.get(
                "raw_response",
                f"领域: {intent_result.get('domain')}, 文档类型: {intent_result.get('doc_type')}",
            )
            await _publish_node_complete("intent_analysis", "意图分析完成", intent_detail)
            await _publish_node_start(
                "feasibility_study",
                "正在评估研究可行性...",
                f"正在分析主题: {context.topic[:30]}...",
            )

            # Step 2 & 3: Feasibility + Deep Research (combined in execute)
            logger.info("step_investigation", task_id=context.task_id)
            investigation_result = await investigator.execute(context)
            workflow_results["steps_completed"].append("feasibility_study")
            workflow_results["steps_completed"].append("deep_research")
            workflow_results["outputs"]["investigation"] = investigation_result

            # Publish node events - 显示模型返回的原始信息(完整文字内容)
            lit_review = investigation_result.get("literature_review", "")
            feasibility_detail = investigation_result.get(
                "raw_response_feasibility", investigation_result.get("feasibility", "N/A")
            )
            deep_research_detail = investigation_result.get("raw_response_research", lit_review)

            await _publish_node_complete(
                "feasibility_study",
                f"可行性评估完成: {investigation_result.get('feasibility', 'N/A')}",
                feasibility_detail,
            )
            await _publish_node_start(
                "deep_research",
                "正在进行深度文献研究...",
                f"文献研究进行中，已生成 {len(investigation_result.get('literature_review', ''))} 字符",
            )

            # Early exit if not feasible (检查大小写)
            if investigation_result.get("feasibility", "").upper() == "FAIL":
                return {
                    "status": "failed",
                    "reason": investigation_result.get("reason", "Not feasible"),
                    "results": workflow_results,
                }

            # Step 4: Drafting
            logger.info("step_drafting", task_id=context.task_id)
            draft_len = 0
            investigator_data = {
                "feasibility_data": investigation_result.get("feasibility_data", {}),
                "literature_review": lit_review,
            }
            draft_result = await writer.execute(context, investigator_data)
            workflow_results["steps_completed"].append("drafting")
            workflow_results["outputs"]["draft"] = draft_result

            # Publish node events - 显示模型生成的完整原始初稿
            draft_len = len(draft_result.get("draft", ""))
            draft_content = draft_result.get("raw_response", draft_result.get("draft", ""))
            draft_detail = draft_content

            await _publish_node_complete(
                "deep_research",
                f"文献研究完成，生成了约{len(lit_review)}字符的综述",
                deep_research_detail,
            )
            await _publish_node_start(
                "drafting",
                f"正在撰写论文初稿（约{draft_len}字符）...",
                f"正在撰写初稿，已完成 {draft_len} 字符",
            )

            # Step 5 & 6: Logic Validation + Plagiarism (combined in execute)
            logger.info("step_review", task_id=context.task_id)
            draft_content = draft_result.get("draft", "")
            review_result = await reviewer.execute(context, draft_content)
            workflow_results["steps_completed"].append("logic_validation")
            workflow_results["steps_completed"].append("plagiarism_check")
            workflow_results["outputs"]["review"] = review_result

            # Publish node events - 显示模型返回的完整原始信息
            await _publish_node_complete(
                "drafting", f"初稿撰写完成，长度约{draft_len}字符", draft_detail
            )
            await _publish_node_start(
                "logic_validation", "正在进行逻辑验证和查重...", "模型正在验证初稿逻辑..."
            )

            # Review completion events - 显示模型原始返回内容
            review_status = review_result.get("status", "UNKNOWN")
            logic_detail = review_result.get("raw_response_logic", f"验证状态: {review_status}")
            plagiarism_data = review_result.get("plagiarism_check", {})
            plagiarism_detail = review_result.get(
                "raw_response_plagiarism",
                f"相似率: {plagiarism_data.get('similarityRate', 'N/A')}%",
            )
            similarity_rate = plagiarism_data.get("similarityRate", "N/A")

            await _publish_node_complete(
                "logic_validation", f"验证完成: {review_status}", logic_detail
            )
            await _publish_node_complete(
                "plagiarism_check", f"查重完成，相似率 {similarity_rate}%", plagiarism_detail
            )
            await _publish_node_start(
                "polishing", "正在进行文档润色和去AI化...", "开始进行文档润色和去AI化处理..."
            )

            # Step 7: Polishing (Editor exclusive)
            logger.info("step_polishing", task_id=context.task_id)
            polished = await self.perform_polishing(context, draft_content)
            workflow_results["steps_completed"].append("polishing")
            workflow_results["outputs"]["polished"] = polished

            # Publish polishing completion - 显示模型润色的完整原始内容
            polished_content = polished.get("polished_content", "")
            polishing_detail = polished.get("raw_response", polished_content)
            await _publish_node_complete("polishing", "文档润色完成", polishing_detail)
            await _publish_node_start(
                "publishing", "正在保存和发布文档...", "正在保存文档到输出目录..."
            )

            # Step 8: Publishing (Editor exclusive)
            logger.info("step_publishing", task_id=context.task_id)
            published = await self.perform_publishing(context, polished_content)
            workflow_results["steps_completed"].append("publishing")
            workflow_results["outputs"]["publish"] = published

            # Publish final completion - 显示最终文件路径
            output_path = published.get("output_path", "")
            publishing_detail = output_path
            await _publish_node_complete(
                "publishing", f"文档已保存: {output_path}", publishing_detail
            )
            # 确保task_uuid不为None
            if task_uuid:
                update_task_status(task_uuid, "COMPLETED", output_path)
                _update_current_node("publishing")

            logger.info("workflow_completed", task_id=context.task_id)
            return {"status": "completed", "results": workflow_results}

        except Exception as e:
            # Publish failure event
            try:
                if task_uuid:
                    update_task_status(task_uuid, "FAILED", error_message=str(e))
            except Exception as update_err:
                logger.warning(
                    "Failed to update task status on error",
                    task_id=context.task_id,
                    error=str(update_err),
                )
            logger.exception("workflow_error", task_id=context.task_id)
            return {"status": "failed", "error": str(e), "results": workflow_results}
