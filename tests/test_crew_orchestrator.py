import pytest
import asyncio

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
