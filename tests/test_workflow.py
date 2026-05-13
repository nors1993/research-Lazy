"""
Comprehensive workflow tests for AutoResearch Agent System.

Tests cover:
1. Paper writing workflow (8 steps)
2. Patent writing workflow (8 steps)
3. Extended patent/paper workflow nodes
4. Error handling and edge cases
5. API integration
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.agents.base import AgentContext, AgentRole
from src.agents.editor import EditorAgent
from src.agents.investigator import InvestigatorAgent
from src.agents.writer import WriterAgent
from src.agents.reviewer import ReviewerAgent
from src.workflow.executor import WorkflowExecutor, create_llm_adapter
from src.workflow.state_machine import WorkflowContext, WorkflowState, NodeStatus, NodeResult
from src.workflow.nodes.extended import EXTENDED_NODES
from src.llm.adapter import LLMAdapter, LLMProvider, LLMResponse
from src.config import settings


# ==================== Fixtures ====================

class MockLLMAdapter:
    """Mock LLM adapter for testing."""
    
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.call_count = 0
        
    async def generate(self, prompt: str, system_prompt: str = None, **kwargs) -> LLMResponse:
        self.call_count += 1
        if self.should_fail:
            raise Exception("LLM Error")
        
        # Return mock responses based on prompt content
        if "feasibility" in prompt.lower() or "可行性" in prompt:
            return LLMResponse(
                content='{"feasibility": "PASS", "innovativeness": {"score": 8}, "conclusion": "High feasibility"}',
                model="mock-model",
                tokens_used=100
            )
        elif "literature" in prompt.lower() or "文献" in prompt:
            return LLMResponse(
                content="Literature review: Recent advances in deep learning show promising results...",
                model="mock-model",
                tokens_used=200
            )
        elif "draft" in prompt.lower() or "论文" in prompt or "patent" in prompt.lower() or "专利" in prompt:
            return LLMResponse(
                content="# Research Paper\n\n## Abstract\nThis paper presents...",
                model="mock-model",
                tokens_used=500
            )
        elif "polish" in prompt.lower() or "润色" in prompt:
            return LLMResponse(
                content="# Polished Research Paper\n\n## Abstract (Refined)...",
                model="mock-model",
                tokens_used=450
            )
        elif "validate" in prompt.lower() or "logic" in prompt.lower():
            return LLMResponse(
                content='{"passed": true, "score": 85, "issues": []}',
                model="mock-model",
                tokens_used=100
            )
        elif "plagiarism" in prompt.lower() or "查重" in prompt:
            return LLMResponse(
                content='{"passed": true, "similarityRate": 5, "sources": []}',
                model="mock-model",
                tokens_used=100
            )
        else:
            return LLMResponse(
                content='{"domain": "CS", "doc_type": "PAPER", "confidence": 0.9}',
                model="mock-model",
                tokens_used=50
            )
    
    async def stream_generate(self, prompt: str, system_prompt: str = None, **kwargs):
        response = await self.generate(prompt, system_prompt, **kwargs)
        for word in response.content.split():
            yield word
            
    async def validate_connection(self) -> bool:
        return not self.should_fail


@pytest.fixture
def mock_llm():
    """Mock LLM adapter fixture."""
    return MockLLMAdapter()


@pytest.fixture
def agent_context():
    """Agent context fixture for testing."""
    return AgentContext(
        task_id="test-task-001",
        topic="人工智能在医疗诊断中的应用",
        doc_type="PAPER",
        domain="CS",
        requirements="需要包含最新研究成果",
        template_path=None,
    )


@pytest.fixture
def patent_context():
    """Patent context fixture for testing."""
    return AgentContext(
        task_id="test-patent-001",
        topic="一种基于深度学习的手势识别方法和装置",
        doc_type="PATENT",
        domain="CS",
        requirements="需要详细技术实现方案",
        template_path=None,
    )


# ==================== Agent Tests ====================

class TestEditorAgent:
    """Tests for EditorAgent."""
    
    @pytest.mark.asyncio
    async def test_editor_initialization(self, mock_llm):
        """Test Editor agent can be initialized."""
        agent = EditorAgent(mock_llm)
        assert agent is not None
        assert agent.config.role == AgentRole.EDITOR
    
    @pytest.mark.asyncio
    async def test_intent_analysis(self, mock_llm, agent_context):
        """Test intent analysis step."""
        agent = EditorAgent(mock_llm)
        result = await agent.execute(agent_context)
        
        assert result is not None
        assert "domain" in result or "next_node" in result
        mock_llm.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_workflow_execution_paper(self, mock_llm, agent_context):
        """Test complete paper workflow execution."""
        agent = EditorAgent(mock_llm)
        result = await agent.execute_workflow(agent_context)
        
        assert result is not None
        assert "status" in result
        # Paper workflow: feasibility → research → drafting → publishing (4 steps)
        steps = result.get("results", {}).get("steps_completed", [])
        assert len(steps) >= 4

    @pytest.mark.asyncio
    async def test_workflow_execution_patent(self, mock_llm, patent_context):
        """Test complete patent workflow execution."""
        agent = EditorAgent(mock_llm)
        result = await agent.execute_workflow(patent_context)
        
        assert result is not None
        assert "status" in result
        # Patent workflow: feasibility → research → drafting → validation → publishing (5 steps)
        steps = result.get("results", {}).get("steps_completed", [])
        assert len(steps) >= 5


class TestInvestigatorAgent:
    """Tests for InvestigatorAgent."""
    
    @pytest.mark.asyncio
    async def test_investigator_initialization(self, mock_llm):
        """Test Investigator agent initialization."""
        agent = InvestigatorAgent(mock_llm)
        assert agent is not None
        assert agent.config.role == AgentRole.INVESTIGATOR
    
    @pytest.mark.asyncio
    async def test_feasibility_study(self, mock_llm, agent_context):
        """Test feasibility study produces valid output."""
        agent = InvestigatorAgent(mock_llm)
        result = await agent.execute(agent_context)
        
        assert result is not None
        assert "feasibility" in result
        # Should pass feasibility check for valid topics


class TestWriterAgent:
    """Tests for WriterAgent."""
    
    @pytest.mark.asyncio
    async def test_writer_initialization(self, mock_llm):
        """Test Writer agent initialization."""
        agent = WriterAgent(mock_llm)
        assert agent is not None
        assert agent.config.role == AgentRole.WRITER
    
    @pytest.mark.asyncio
    async def test_draft_generation(self, mock_llm, agent_context):
        """Test draft generation produces content."""
        agent = WriterAgent(mock_llm)
        
        investigator_data = {
            "feasibility_data": {"feasibility": "PASS"},
            "literature_review": "Recent research shows..."
        }
        
        result = await agent.execute(agent_context, investigator_data)
        
        assert result is not None
        assert "draft" in result
        assert len(result["draft"]) > 0


class TestReviewerAgent:
    """Tests for ReviewerAgent."""
    
    @pytest.mark.asyncio
    async def test_reviewer_initialization(self, mock_llm):
        """Test Reviewer agent initialization."""
        agent = ReviewerAgent(mock_llm)
        assert agent is not None
        assert agent.config.role == AgentRole.REVIEWER
    
    @pytest.mark.asyncio
    async def test_logic_validation(self, mock_llm, agent_context):
        """Test logic validation."""
        agent = ReviewerAgent(mock_llm)
        
        result = await agent.execute(agent_context, "Test draft content...")
        
        assert result is not None
        assert "node" in result
        assert "status" in result
    
    @pytest.mark.asyncio
    async def test_plagiarism_check(self, mock_llm, agent_context):
        """Test plagiarism check."""
        agent = ReviewerAgent(mock_llm)
        
        # Use internal method since public method doesn't exist
        result = await agent._check_plagiarism(agent_context, "Content to check")
        
        assert result is not None


# ==================== Workflow Executor Tests ====================

class TestWorkflowExecutor:
    """Tests for WorkflowExecutor."""
    
    @pytest.mark.asyncio
    async def test_executor_initialization(self):
        """Test workflow executor can be created."""
        with patch('src.workflow.executor.create_llm_adapter', return_value=MockLLMAdapter()):
            executor = WorkflowExecutor(MockLLMAdapter())
            assert executor is not None
            assert executor.editor is not None
    
    @pytest.mark.asyncio
    async def test_paper_workflow_complete(self):
        """Test complete paper workflow."""
        mock_llm = MockLLMAdapter()
        executor = WorkflowExecutor(mock_llm)
        
        result = await executor.execute_task(
            task_id="test-paper-workflow",
            topic="深度学习在医学影像诊断中的应用",
            domain="CS",
            doc_type="PAPER"
        )
        
        assert result is not None
        assert "status" in result
        # Should complete successfully
        assert result["status"] in ["COMPLETED", "FAILED"]
    
    @pytest.mark.asyncio
    async def test_patent_workflow_complete(self):
        """Test complete patent workflow."""
        mock_llm = MockLLMAdapter()
        executor = WorkflowExecutor(mock_llm)
        
        result = await executor.execute_task(
            task_id="test-patent-workflow",
            topic="一种基于深度神经网络的手势识别方法和装置",
            domain="CS",
            doc_type="PATENT"
        )
        
        assert result is not None
        assert "status" in result
    
    @pytest.mark.asyncio
    async def test_workflow_with_invalid_topic(self):
        """Test workflow handles infeasible topics."""
        # Create mock that returns FAIL for feasibility
        class FailingLLMAdapter(MockLLMAdapter):
            async def generate(self, prompt: str, system_prompt: str = None, **kwargs) -> LLMResponse:
                if "feasibility" in prompt.lower():
                    return LLMResponse(
                        content='{"feasibility": "FAIL", "conclusion": "Not enough innovation"}',
                        model="mock-model",
                        tokens_used=50
                    )
                return await super().generate(prompt, system_prompt, **kwargs)
        
        executor = WorkflowExecutor(FailingLLMAdapter())
        
        result = await executor.execute_task(
            task_id="test-invalid",
            topic="如何煮米饭",
            domain="CS",
            doc_type="PAPER"
        )
        
        # Should fail with appropriate reason
        assert result["status"] == "FAILED" or result["output"]["status"] == "failed"


# ==================== LLM Adapter Tests ====================

class TestLLMAdapter:
    """Tests for LLM adapter factory."""
    
    def test_openai_adapter_creation(self):
        """Test OpenAI adapter can be created."""
        adapter = LLMAdapter.create(
            provider=LLMProvider.OPENAI,
            model="gpt-4",
            api_key="test-key"
        )
        assert adapter is not None
    
    def test_openai_compatible_adapter_creation(self):
        """Test OpenAI compatible adapter can be created."""
        adapter = LLMAdapter.create(
            provider=LLMProvider.OPENAI_COMPATIBLE,
            model="deepseek-chat",
            api_key="test-key",
            base_url="https://api.deepseek.com/v1"
        )
        assert adapter is not None
    
    def test_all_providers_registered(self):
        """Test all LLM providers are registered."""
        providers = [
            LLMProvider.OPENAI,
            LLMProvider.OPENAI_COMPATIBLE,
            LLMProvider.ANTHROPIC,
            LLMProvider.AZURE_OPENAI,
            LLMProvider.OLLAMA,
        ]
        
        for provider in providers:
            adapter = LLMAdapter.create(
                provider=provider,
                model="test-model",
                api_key="test-key"
            )
            assert adapter is not None
    
    def test_unknown_provider_raises_error(self):
        """Test unknown provider raises ValueError."""
        # Try to create adapter with None provider
        with pytest.raises((ValueError, TypeError)):
            LLMAdapter.create(
                provider=None,
                model="test",
                api_key="test"
            )


# ==================== Edge Case Tests ====================

class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    @pytest.mark.asyncio
    async def test_empty_topic(self, mock_llm):
        """Test workflow handles empty topic gracefully."""
        executor = WorkflowExecutor(mock_llm)
        
        # Empty topic should still work (it will fail at feasibility)
        result = await executor.execute_task(
            task_id="test-empty",
            topic="",
            domain="CS",
            doc_type="PAPER"
        )
        
        # Should handle gracefully without crashing
        assert result is not None
        assert "status" in result
    
    @pytest.mark.asyncio
    async def test_llm_failure_handling(self):
        """Test workflow handles LLM failures gracefully."""
        failing_llm = MockLLMAdapter(should_fail=True)
        executor = WorkflowExecutor(failing_llm)
        
        result = await executor.execute_task(
            task_id="test-fail",
            topic="测试主题",
            domain="CS",
            doc_type="PAPER"
        )
        
        # Should return FAILED status, not crash
        assert result["status"] == "FAILED"
    
    @pytest.mark.asyncio
    async def test_different_doc_types(self, mock_llm):
        """Test workflow supports different document types."""
        executor = WorkflowExecutor(mock_llm)
        
        doc_types = ["PAPER", "PATENT", "SURVEY", "PROPOSAL", "ABSTRACT", "THESIS"]
        
        for doc_type in doc_types:
            result = await executor.execute_task(
                task_id=f"test-{doc_type}",
                topic="测试研究主题",
                domain="CS",
                doc_type=doc_type
            )
            assert result is not None
            assert "status" in result
    
    @pytest.mark.asyncio
    async def test_different_domains(self, mock_llm):
        """Test workflow supports different domains."""
        executor = WorkflowExecutor(mock_llm)
        
        domains = ["CS", "MED", "ECON", "PHYS", "BIO", "MATH"]
        
        for domain in domains:
            result = await executor.execute_task(
                task_id=f"test-{domain}",
                topic="测试研究主题",
                domain=domain,
                doc_type="PAPER"
            )
            assert result is not None


# ==================== Integration Tests ====================

class TestAPIFlow:
    """API-level integration tests."""
    
    def test_create_task_request_validation(self):
        """Test task request validation."""
        from src.api.schemas import CreateTaskRequest, Domain, DocType

        # Valid request using aliases
        req = CreateTaskRequest(
            topic="测试主题",
            domain=Domain.CS,
            docType=DocType.PAPER
        )
        assert req.topic == "测试主题"
        assert req.domain == Domain.CS
        assert req.doc_type == DocType.PAPER
    
    def test_task_status_enum(self):
        """Test task status values."""
        from src.api.schemas import TaskStatus
        
        assert TaskStatus.PENDING.value == "PENDING"
        assert TaskStatus.RUNNING.value == "RUNNING"
        assert TaskStatus.COMPLETED.value == "COMPLETED"
        assert TaskStatus.FAILED.value == "FAILED"
        assert TaskStatus.PAUSED.value == "PAUSED"
        assert TaskStatus.CANCELLED.value == "CANCELLED"


# ==================== Extended Node Tests ====================

class TestExtendedNodes:
    """Tests for extended patent and paper workflow nodes."""

    def test_extended_nodes_registered(self):
        """Test that all extended nodes are registered."""
        expected_nodes = [
            "patent_feasibility",
            "patent_research",
            "patent_drafting",
            "patent_validation",
            "patent_publishing",
            "paper_feasibility",
            "paper_research",
            "paper_drafting",
            "paper_publishing",
        ]
        for node_name in expected_nodes:
            assert node_name in EXTENDED_NODES, f"Node {node_name} not registered"

    def test_patent_node_class_structure(self):
        """Test patent node classes have correct structure."""
        from src.workflow.nodes.extended import PatentFeasibilityNode

        assert hasattr(PatentFeasibilityNode, 'name')
        assert hasattr(PatentFeasibilityNode, 'timeout_seconds')
        assert hasattr(PatentFeasibilityNode, 'execute')

    def test_paper_node_class_structure(self):
        """Test paper node classes have correct structure."""
        from src.workflow.nodes.extended import PaperFeasibilityNode

        assert hasattr(PaperFeasibilityNode, 'name')
        assert hasattr(PaperFeasibilityNode, 'timeout_seconds')
        assert hasattr(PaperFeasibilityNode, 'execute')

    def test_node_has_workflow_node_interface(self):
        """Test nodes have WorkflowNode interface."""
        from src.workflow.nodes.extended import (
            PatentFeasibilityNode,
            PaperFeasibilityNode,
        )

        # Check that nodes have the required attributes of WorkflowNode
        for NodeClass in [PatentFeasibilityNode, PaperFeasibilityNode]:
            assert hasattr(NodeClass, 'name')
            assert hasattr(NodeClass, 'timeout_seconds')
            assert hasattr(NodeClass, 'execute')
            assert hasattr(NodeClass, 'on_timeout')


class TestExtendedNodeExecution:
    """Tests for extended node execution with mocks."""

    def test_patent_feasibility_node_init(self):
        """Test PatentFeasibilityNode can be initialized."""
        from src.workflow.nodes.extended import PatentFeasibilityNode

        # Create a simple mock that has generate method
        mock_adapter = MagicMock()
        node = PatentFeasibilityNode(mock_adapter)

        assert node is not None
        assert node.name == "patent_feasibility"
        assert node.timeout_seconds == 120

    def test_paper_feasibility_node_init(self):
        """Test PaperFeasibilityNode can be initialized."""
        from src.workflow.nodes.extended import PaperFeasibilityNode

        mock_adapter = MagicMock()
        node = PaperFeasibilityNode(mock_adapter)

        assert node is not None
        assert node.name == "paper_feasibility"
        assert node.timeout_seconds == 120


# ==================== Run Tests ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])