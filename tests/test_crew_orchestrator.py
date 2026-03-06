import pytest
import asyncio
import json
from unittest.mock import MagicMock, AsyncMock

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.crew_orchestrator import CrewOrchestrator
from src.memory_gateway import MemoryGateway
from src.identity_manager import UserContext, UserRole


class DummyAgent:
    def __init__(self):
        self.received = {}
        self.is_fast_agent = True

    async def execute(self, user_message=None, context=None):
        self.received['user_message'] = user_message
        self.received['context'] = context
        return "DUMMY"


@pytest.mark.asyncio
async def test_execute_request_uses_gateway_for_history(monkeypatch):
    # prepare a fake gateway that records arguments
    captured = {}

    async def fake_fetch(user_ctx, chat_id, limit=15):
        captured['args'] = (user_ctx, chat_id, limit)
        return [
            {'role': 'user', 'content': 'hi'},
            {'role': 'assistant', 'content': 'hello'}
        ]

    gateway = MemoryGateway()
    monkeypatch.setattr(gateway, 'fetch_working_memory', fake_fetch)

    orchestrator = CrewOrchestrator(memory_gateway=gateway)
    dummy = DummyAgent()
    monkeypatch.setattr(orchestrator.agents, 'create_agent', lambda key: dummy)

    user = UserContext(telegram_id='u1', name='Test', role=UserRole.EXTERNAL)
    # execute_request should forward the user and chat history into agent
    response = await orchestrator.execute_request(
        user_message='hey',
        target_agent_key='any',
        chat_id=42,
        user=user,
        extra_context=None,
    )

    assert response == "DUMMY"
    # gateway called with correct parameters
    assert captured['args'] == (user, 42, 15)
    # the dummy agent should have seen a context string containing chat history
    assert 'CHAT HISTORY' in dummy.received['context']
    assert 'user: hi' in dummy.received['context']


@pytest.mark.asyncio
async def test_execute_request_without_history_does_not_call_gateway(monkeypatch):
    gateway = MemoryGateway()
    called = False

    async def fake_fetch(*args, **kwargs):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(gateway, 'fetch_working_memory', fake_fetch)
    orchestrator = CrewOrchestrator(memory_gateway=gateway)
    dummy = DummyAgent()
    monkeypatch.setattr(orchestrator.agents, 'create_agent', lambda key: dummy)

    # omit chat_id or user
    res = await orchestrator.execute_request(user_message='x', target_agent_key='y')
    assert res == "DUMMY"
    assert not called


def test_format_identity_context_with_user(monkeypatch):
    gateway = MagicMock()
    orchestrator = CrewOrchestrator(memory_gateway=gateway)
    user = UserContext(
        telegram_id='123', 
        name='Alice', 
        role=UserRole.ADMIN, 
        description="Admin user"
    )
    
    context = orchestrator._format_identity_context(user)
    assert "Alice" in context
    assert str(UserRole.ADMIN) in context
    assert "Admin user" in context


def test_format_identity_context_without_user(monkeypatch):
    gateway = MagicMock()
    orchestrator = CrewOrchestrator(memory_gateway=gateway)
    assert orchestrator._format_identity_context(None) == ""


def test_clean_and_extract_json(monkeypatch):
    gateway = MagicMock()
    orchestrator = CrewOrchestrator(memory_gateway=gateway)

    # Valid JSON
    assert orchestrator._clean_and_extract_json('{"a": 1}') == {"a": 1}

    # Markdown JSON
    assert orchestrator._clean_and_extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    
    # Text around JSON
    assert orchestrator._clean_and_extract_json('Here is json: {"a": 1} thanks') == {"a": 1}

    # Single quotes (fallback attempt)
    assert orchestrator._clean_and_extract_json("{'a': 1}") == {"a": 1}

    # Invalid JSON
    assert orchestrator._clean_and_extract_json('Not a json') is None


@pytest.mark.asyncio
async def test_zero_shot_routing_success(monkeypatch):
    gateway = MagicMock()
    orchestrator = CrewOrchestrator(memory_gateway=gateway)
    
    # Mock agents config
    mock_agents = MagicMock()
    # Need to simulate that 'AGENT_A' is a valid agent in config
    mock_agents.config = {'agent_a': {}, 'agent_b': {}}
    mock_agents.get_zero_shot_hypothesis.return_value = {
        'agent_a': 'Hypothesis A',
        'agent_b': 'Hypothesis B'
    }
    monkeypatch.setattr(orchestrator, 'agents', mock_agents)

    # Mock ZeroShotClient
    mock_client = MagicMock()
    # classify returns dict of scores
    mock_client.classify.return_value = {
        'Hypothesis A': 0.9,
        'Hypothesis B': 0.1
    }
    monkeypatch.setattr(orchestrator, 'zero_shot_client', mock_client)

    result = await orchestrator._zero_shot_routing("some message")
    # The orchestrator returns upper case agent key
    assert result == "AGENT_A"


@pytest.mark.asyncio
async def test_zero_shot_routing_low_confidence(monkeypatch):
    gateway = MagicMock()
    orchestrator = CrewOrchestrator(memory_gateway=gateway)
    
    mock_agents = MagicMock()
    mock_agents.config = {'agent_a': {}, 'agent_b': {}}
    mock_agents.get_zero_shot_hypothesis.return_value = {
        'agent_a': 'Hypothesis A',
        'agent_b': 'Hypothesis B'
    }
    monkeypatch.setattr(orchestrator, 'agents', mock_agents)

    mock_client = MagicMock()
    # Both low scores. Logic requires max_norm_score > 0.39 (normalized)
    # If raw scores are low but one dominates, normalization might boost it.
    # But let's verify normalization logic:
    # 0.1, 0.1 -> sum=0.2. Normalized -> 0.5, 0.5.
    # Max norm = 0.5 > 0.39.
    # BUT margin check: top - second = 0.5 - 0.5 = 0 < 0.1 -> Margin fail.
    mock_client.classify.return_value = {
        'Hypothesis A': 0.1,
        'Hypothesis B': 0.1
    }
    monkeypatch.setattr(orchestrator, 'zero_shot_client', mock_client)

    result = await orchestrator._zero_shot_routing("some message")
    assert result is None


@pytest.mark.asyncio
async def test_zero_shot_routing_exception(monkeypatch):
    gateway = MagicMock()
    orchestrator = CrewOrchestrator(memory_gateway=gateway)
    
    # Mock zero_shot_client to raise exception
    mock_client = MagicMock()
    mock_client.classify.side_effect = Exception("API Error")
    monkeypatch.setattr(orchestrator, 'zero_shot_client', mock_client)

    # Mock agents config to avoid earlier failures
    mock_agents = MagicMock()
    mock_agents.get_zero_shot_hypothesis.return_value = {'agent_a': 'Hypothesis A'}
    monkeypatch.setattr(orchestrator, 'agents', mock_agents)

    result = await orchestrator._zero_shot_routing("message")
    assert result is None


@pytest.mark.asyncio
async def test_zero_shot_routing_no_valid_agents_after_filter(monkeypatch):
    gateway = MagicMock()
    orchestrator = CrewOrchestrator(memory_gateway=gateway)
    
    # Agents config does NOT contain agent_a
    mock_agents = MagicMock()
    mock_agents.config = {} 
    mock_agents.get_zero_shot_hypothesis.return_value = {'agent_a': 'Hypothesis A'}
    monkeypatch.setattr(orchestrator, 'agents', mock_agents)

    mock_client = MagicMock()
    mock_client.classify.return_value = {'Hypothesis A': 0.9}
    monkeypatch.setattr(orchestrator, 'zero_shot_client', mock_client)

    result = await orchestrator._zero_shot_routing("message")
    assert result is None


@pytest.mark.asyncio
async def test_route_request_zero_shot_hit(monkeypatch):
    gateway = MagicMock()
    orchestrator = CrewOrchestrator(memory_gateway=gateway)
    
    # Mock _zero_shot_routing directly to return an agent
    # We need to make it an async function or use AsyncMock properly if it was called directly.
    # In code: result = await self._zero_shot_routing(user_message)
    # so we need an awaitable.
    async def mock_zero_shot(msg):
        return "AGENT_A"
    
    monkeypatch.setattr(orchestrator, '_zero_shot_routing', mock_zero_shot)
    
    result = await orchestrator.route_request("hello", user=None)
    assert result == "AGENT_A"


@pytest.mark.asyncio
async def test_route_request_classic_fallback(monkeypatch):
    gateway = MagicMock()
    orchestrator = CrewOrchestrator(memory_gateway=gateway)
    
    # Mock _zero_shot_routing to return None
    async def mock_zero_shot_fail(msg):
        return None
    monkeypatch.setattr(orchestrator, '_zero_shot_routing', mock_zero_shot_fail)

    # Mock agents and dispatcher
    mock_agents = MagicMock()
    mock_dispatcher = AsyncMock()
    mock_dispatcher.is_fast_agent = True
    # Dispatcher returns JSON pointing to Agent B
    mock_dispatcher.execute.return_value = '{"target_agent": "AGENT_B"}'
    
    mock_agents.create_agent.return_value = mock_dispatcher
    # Ensure agent_b is in config so validation passes
    mock_agents.config = {"agent_b": {}} 
    mock_agents.get_agents_summary.return_value = "Summary"
    
    monkeypatch.setattr(orchestrator, 'agents', mock_agents)
    
    result = await orchestrator.route_request("help", user=None)
    assert result == "AGENT_B"


@pytest.mark.asyncio
async def test_route_request_multimodal_fallback(monkeypatch):
    gateway = MagicMock()
    orchestrator = CrewOrchestrator(memory_gateway=gateway)
    
    mock_agents = MagicMock()
    mock_dispatcher = AsyncMock()
    mock_dispatcher.is_fast_agent = True
    mock_dispatcher.execute.return_value = '{"target_agent": "VISION_AGENT"}'
    
    mock_agents.create_agent.return_value = mock_dispatcher
    mock_agents.config = {"vision_agent": {}}
    mock_agents.get_agents_summary.return_value = "Summary"
    
    monkeypatch.setattr(orchestrator, 'agents', mock_agents)

    # Multimodal message
    message = [{"type": "text", "text": "look"}, {"type": "image_url", "image_url": "url"}]
    
    result = await orchestrator.route_request(message, user=None)
    
    assert result == "VISION_AGENT"
    assert mock_dispatcher.model_name == "vision-model"


@pytest.mark.asyncio
async def test_run_consolidation_task(monkeypatch):
    gateway = MagicMock()
    orchestrator = CrewOrchestrator(memory_gateway=gateway)
    
    mock_agents = MagicMock()
    mock_consolidator = AsyncMock()
    mock_consolidator.execute.return_value = '[]'
    
    mock_agents.create_agent.return_value = mock_consolidator
    monkeypatch.setattr(orchestrator, 'agents', mock_agents)
    
    # Mock tasks config
    mock_tasks = MagicMock()
    mock_tasks.config = {'memory_consolidation': {'description': 'desc {conversation_history} {categories} {types}'}}
    monkeypatch.setattr(orchestrator, 'tasks', mock_tasks)
    
    user = UserContext(telegram_id='123', name='test', role=UserRole.EXTERNAL)
    
    res = await orchestrator.run_consolidation_task("history", user)
    assert res == '[]'


@pytest.mark.asyncio
async def test_run_consolidation_task_exception(monkeypatch):
    gateway = MagicMock()
    orchestrator = CrewOrchestrator(memory_gateway=gateway)
    
    mock_agents = MagicMock()
    mock_consolidator = AsyncMock()
    mock_consolidator.execute.side_effect = Exception("LLM Error")
    
    mock_agents.create_agent.return_value = mock_consolidator
    monkeypatch.setattr(orchestrator, 'agents', mock_agents)
    
    mock_tasks = MagicMock()
    mock_tasks.config = {'memory_consolidation': {'description': 'desc'}}
    monkeypatch.setattr(orchestrator, 'tasks', mock_tasks)
    
    user = UserContext(telegram_id='123', name='test', role=UserRole.EXTERNAL)
    
    res = await orchestrator.run_consolidation_task("history", user)
    assert res == "[]"


@pytest.mark.asyncio
async def test_execute_request_slow_agent_path(monkeypatch):
    gateway = MagicMock()
    orchestrator = CrewOrchestrator(memory_gateway=gateway)
    
    mock_agents = MagicMock()
    mock_agent = MagicMock()
    # Ensure is_fast_agent is False or not present
    if hasattr(mock_agent, "is_fast_agent"):
        del mock_agent.is_fast_agent
    
    mock_agents.create_agent.return_value = mock_agent
    monkeypatch.setattr(orchestrator, 'agents', mock_agents)

    # Mock tasks
    mock_tasks = MagicMock()
    mock_tasks.analysis_task.return_value = MagicMock()
    mock_tasks.response_task.return_value = MagicMock()
    monkeypatch.setattr(orchestrator, 'tasks', mock_tasks)

    # Mock Crew
    mock_crew_cls = MagicMock()
    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.return_value = "Slow Response"
    mock_crew_cls.return_value = mock_crew_instance
    monkeypatch.setattr('src.crew_orchestrator.Crew', mock_crew_cls)

    # Test with text message
    result = await orchestrator.execute_request("slow message", "slow_agent", user=None)
    assert result == "Slow Response"
    mock_crew_instance.kickoff.assert_called_once()


@pytest.mark.asyncio
async def test_execute_request_slow_agent_multimodal(monkeypatch):
    gateway = MagicMock()
    orchestrator = CrewOrchestrator(memory_gateway=gateway)
    
    mock_agents = MagicMock()
    mock_agent = MagicMock()
    # Ensure is_fast_agent is False
    if hasattr(mock_agent, "is_fast_agent"):
        del mock_agent.is_fast_agent
    
    mock_agents.create_agent.return_value = mock_agent
    monkeypatch.setattr(orchestrator, 'agents', mock_agents)

    mock_tasks = MagicMock()
    mock_tasks.analysis_task.return_value = MagicMock()
    mock_tasks.response_task.return_value = MagicMock()
    monkeypatch.setattr(orchestrator, 'tasks', mock_tasks)

    mock_crew_cls = MagicMock()
    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.return_value = "Slow Multimodal Response"
    mock_crew_cls.return_value = mock_crew_instance
    monkeypatch.setattr('src.crew_orchestrator.Crew', mock_crew_cls)

    # Test with multimodal message
    multimodal_msg = [{"type": "text", "text": "analyze this"}, {"type": "image_url", "image_url": "..."}]
    result = await orchestrator.execute_request(multimodal_msg, "vision_agent", user=None)
    
    assert result == "Slow Multimodal Response"
    # Verify extraction of text content
    args, _ = mock_tasks.analysis_task.call_args
    assert "[User sent an image]: analyze this" in args[1]


@pytest.mark.asyncio
async def test_execute_request_exception_in_slow_path(monkeypatch):
    gateway = MagicMock()
    orchestrator = CrewOrchestrator(memory_gateway=gateway)
    
    mock_agents = MagicMock()
    mock_agent = MagicMock()
    if hasattr(mock_agent, "is_fast_agent"):
        del mock_agent.is_fast_agent
    mock_agents.create_agent.return_value = mock_agent
    monkeypatch.setattr(orchestrator, 'agents', mock_agents)

    mock_tasks = MagicMock()
    monkeypatch.setattr(orchestrator, 'tasks', mock_tasks)

    # Crew instantiation fails or kickoff fails
    mock_crew_cls = MagicMock()
    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.side_effect = Exception("Crew failed")
    mock_crew_cls.return_value = mock_crew_instance
    monkeypatch.setattr('src.crew_orchestrator.Crew', mock_crew_cls)

    result = await orchestrator.execute_request("msg", "agent", user=None)
    assert "Error executing agent: Crew failed" in result

