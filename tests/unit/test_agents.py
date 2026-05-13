"""Unit tests for core agents."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Optional

from src.agents.base import AgentConfig, AgentContext, AgentRole, BaseAgent
from src.agents.editor import EditorAgent
from src.agents.investigator import InvestigatorAgent
from src.agents.writer import WriterAgent
from src.agents.reviewer import ReviewerAgent
from src.llm.adapter import LLMResponse


class MockLLMAdapter:
    """Mock LLM adapter for testing."""

    def __init__(self, response_content: str = "Mock response"):
        self._response_content = response_content

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> LLMResponse:
        return LLMResponse(
            content=self._response_content,
            model="mock-model",
            tokens_used=10,
        )

    async def stream_generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs):
        for word in self._response_content.split():
            yield word

    async def validate_connection(self) -> bool:
        return True


@pytest.fixture
def mock_llm():
    """Fixture for mock LLM adapter."""
    return MockLLMAdapter()


@pytest.fixture
def agent_context():
    """Fixture for agent context."""
    return AgentContext(
        task_id="test-task-001",
        topic="Test research topic",
        doc_type="PAPER",
        domain="CS",
        requirements="Test requirements",
        template_path=None,
    )


class TestAgentRole:
    """Tests for AgentRole enum."""

    def test_agent_roles(self):
        """Test all agent roles exist."""
        assert AgentRole.EDITOR.value == "editor"
        assert AgentRole.INVESTIGATOR.value == "investigator"
        assert AgentRole.WRITER.value == "writer"
        assert AgentRole.REVIEWER.value == "reviewer"


class TestAgentConfig:
    """Tests for AgentConfig."""

    def test_agent_config_defaults(self):
        """Test agent config default values."""
        config = AgentConfig(
            role=AgentRole.EDITOR,
            system_prompt="Test prompt",
        )
        assert config.role == AgentRole.EDITOR
        assert config.system_prompt == "Test prompt"
        assert config.model == "gpt-4o"
        assert config.temperature == 0.7
        assert config.max_tokens == 4096

    def test_agent_config_custom(self):
        """Test agent config with custom values."""
        config = AgentConfig(
            role=AgentRole.INVESTIGATOR,
            system_prompt="Custom prompt",
            model="gpt-3.5-turbo",
            temperature=0.5,
            max_tokens=2048,
        )
        assert config.model == "gpt-3.5-turbo"
        assert config.temperature == 0.5
        assert config.max_tokens == 2048


class TestAgentContext:
    """Tests for AgentContext."""

    def test_agent_context_creation(self):
        """Test agent context creation."""
        context = AgentContext(
            task_id="task-001",
            topic="AI Research",
            domain="CS",
            doc_type="PAPER",
        )
        assert context.task_id == "task-001"
        assert context.topic == "AI Research"
        assert context.domain == "CS"
        assert context.doc_type == "PAPER"
        assert context.shared_data == {}

    def test_agent_context_with_options(self):
        """Test agent context with optional fields."""
        context = AgentContext(
            task_id="task-002",
            topic="ML Research",
            domain="CS",
            doc_type="PAPER",
            requirements="Focus on deep learning",
            template_path="templates/paper.md",
            shared_data={"key": "value"},
        )
        assert context.requirements == "Focus on deep learning"
        assert context.template_path == "templates/paper.md"
        assert context.shared_data["key"] == "value"


class TestEditorAgent:
    """Tests for EditorAgent."""

    @pytest.mark.asyncio
    async def test_editor_initialization(self, mock_llm):
        """Test editor agent initialization."""
        agent = EditorAgent(mock_llm)
        assert agent.role == AgentRole.EDITOR

    @pytest.mark.asyncio
    async def test_execute_returns_intent_analysis(self, mock_llm, agent_context):
        """Test editor execute returns intent analysis result."""
        agent = EditorAgent(mock_llm)
        result = await agent.execute(agent_context)

        assert "status" in result
        assert result["status"] == "intent_analyzed"
        assert "next_node" in result

    @pytest.mark.asyncio
    async def test_perform_polishing(self, mock_llm, agent_context):
        """Test editor performs polishing."""
        agent = EditorAgent(mock_llm)
        result = await agent.perform_polishing(agent_context, "Original draft content")

        assert "status" in result
        assert result["status"] == "polished"
        assert "polished_content" in result


class TestInvestigatorAgent:
    """Tests for InvestigatorAgent."""

    @pytest.mark.asyncio
    async def test_investigator_initialization(self, mock_llm):
        """Test investigator agent initialization."""
        agent = InvestigatorAgent(mock_llm)
        assert agent.role == AgentRole.INVESTIGATOR

    @pytest.mark.asyncio
    async def test_execute_returns_feasibility_and_research(self, mock_llm, agent_context):
        """Test investigator execute returns both feasibility and research."""
        agent = InvestigatorAgent(mock_llm)
        result = await agent.execute(agent_context)

        # Should have node info and either feasibility PASS or FAIL
        assert "node" in result
        assert "feasibility" in result
        # If PASS, should also have research results
        if result["feasibility"] == "PASS":
            assert "literature_review" in result


class TestWriterAgent:
    """Tests for WriterAgent."""

    @pytest.mark.asyncio
    async def test_writer_initialization(self, mock_llm):
        """Test writer agent initialization."""
        agent = WriterAgent(mock_llm)
        assert agent.role == AgentRole.WRITER

    @pytest.mark.asyncio
    async def test_execute_requires_investigator_data(self, mock_llm, agent_context):
        """Test writer execute requires investigator data."""
        agent = WriterAgent(mock_llm)
        investigator_data = {
            "feasibility_data": {"conclusion": "Feasible"},
            "literature_review": "Literature content",
        }
        result = await agent.execute(agent_context, investigator_data)

        assert "node" in result
        assert result["node"] == "drafting"
        assert "draft" in result

    @pytest.mark.asyncio
    async def test_revise_draft(self, mock_llm, agent_context):
        """Test writer revise method."""
        agent = WriterAgent(mock_llm)
        result = await agent.revise(
            agent_context,
            "Original draft content",
            {"recommendations": ["Improve clarity"], "version": 1},
        )

        assert "node" in result
        assert result["node"] == "drafting"
        assert "draft" in result
        assert result["version"] == 2


class TestReviewerAgent:
    """Tests for ReviewerAgent."""

    @pytest.mark.asyncio
    async def test_reviewer_initialization(self, mock_llm):
        """Test reviewer agent initialization."""
        agent = ReviewerAgent(mock_llm)
        assert agent.role == AgentRole.REVIEWER

    @pytest.mark.asyncio
    async def test_execute_validates_and_checks_plagiarism(self, mock_llm, agent_context):
        """Test reviewer execute validates and checks plagiarism."""
        agent = ReviewerAgent(mock_llm)
        result = await agent.execute(agent_context, "Draft content to review")

        assert "node" in result
        assert "status" in result
        assert "logic_validation" in result
        assert "plagiarism_check" in result
        assert "version" in result

    @pytest.mark.asyncio
    async def test_determine_status(self, mock_llm):
        """Test status determination logic."""
        agent = ReviewerAgent(mock_llm)

        # Approved case
        status = agent._determine_status(
            {"passed": True, "score": 90},
            {"passed": True, "similarityRate": 5},
        )
        assert status == "APPROVED"

        # Major revision case (low logic score)
        status = agent._determine_status(
            {"passed": True, "score": 60},
            {"passed": True, "similarityRate": 5},
        )
        assert status == "MAJOR_REVISION"

        # Rejected case (plagiarism failed)
        status = agent._determine_status(
            {"passed": True, "score": 90},
            {"passed": False, "similarityRate": 20},
        )
        assert status == "REJECTED"


class TestBaseAgentGenerateResponse:
    """Tests for BaseAgent.generate_response."""

    @pytest.mark.asyncio
    async def test_generate_response_with_default_prompt(self, mock_llm):
        """Test generate response with default system prompt."""
        config = AgentConfig(
            role=AgentRole.EDITOR,
            system_prompt="You are a helpful assistant.",
        )
        agent = EditorAgent(mock_llm)  # Use concrete class

        response = await agent.generate_response("Hello, world!")

        assert response.content == "Mock response"
        assert response.model == "mock-model"
        assert response.tokens_used == 10

    @pytest.mark.asyncio
    async def test_generate_response_with_custom_system(self, mock_llm):
        """Test generate response with custom system prompt."""
        agent = EditorAgent(mock_llm)

        response = await agent.generate_response(
            "Test prompt",
            system_prompt="Custom system prompt",
        )

        assert response.content == "Mock response"

    @pytest.mark.asyncio
    async def test_stream_response(self, mock_llm):
        """Test streaming response."""
        agent = EditorAgent(mock_llm)

        chunks = []
        async for chunk in agent.stream_response("Test prompt"):
            chunks.append(chunk)

        assert len(chunks) > 0