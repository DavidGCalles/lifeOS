import pytest
from unittest.mock import MagicMock
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.zero_shot_client import ZeroShotClient

@pytest.fixture
def mock_infinity_client():
    return MagicMock()

@pytest.fixture
def client(mock_infinity_client):
    return ZeroShotClient(infinity_client=mock_infinity_client)

def test_construct_pairs(client):
    text = "Hello world"
    labels = ["greeting", "farewell"]
    expected = [
        "Hello world [SEP] This example is greeting.",
        "Hello world [SEP] This example is farewell."
    ]
    pairs = client._construct_pairs(text, labels)
    assert pairs == expected

def test_construct_pairs_custom_template(client):
    text = "Hello"
    labels = ["A"]
    template = "Category: {}"
    expected = ["Hello [SEP] Category: A"]
    pairs = client._construct_pairs(text, labels, hypothesis_template=template)
    assert pairs == expected

def test_classify_success(client, mock_infinity_client):
    mock_infinity_client.classify.return_value = {
        "data": [
            [
                {"label": "entailment", "score": 0.95},
                {"label": "neutral", "score": 0.03},
                {"label": "contradiction", "score": 0.02}
            ],
            [
                {"label": "entailment", "score": 0.10},
                {"label": "neutral", "score": 0.10},
                {"label": "contradiction", "score": 0.80}
            ]
        ]
    }

    text = "Invest in stocks"
    labels = ["finance", "health"]
    
    result = client.classify(text, labels)
    
    assert result is not None
    assert isinstance(result, dict)
    assert result["finance"] == pytest.approx(0.93)
    assert result["health"] == pytest.approx(-0.70)

    expected_inputs = [
        "Invest in stocks [SEP] User wants to finance.",
        "Invest in stocks [SEP] User wants to health."
    ]
    mock_infinity_client.classify.assert_called_once_with(expected_inputs, raw_scores=False)

def test_classify_empty_labels(client, mock_infinity_client):
    result = client.classify("text", [])
    assert result is None
    mock_infinity_client.classify.assert_not_called()

def test_classify_missing_keys(client, mock_infinity_client):
    mock_infinity_client.classify.return_value = {
        "data": [
            [
                {"label": "entailment", "score": 0.80}
            ],
            [
                {"label": "contradiction", "score": 0.60}
            ],
            [
                {"label": "neutral", "score": 1.0}
            ]
        ]
    }

    text = "Some text"
    labels = ["A", "B", "C"]
    
    result = client.classify(text, labels)
    
    assert result is not None
    assert isinstance(result, dict)
    assert result["A"] == pytest.approx(0.80)
    assert result["B"] == pytest.approx(-0.60)
    assert result["C"] == pytest.approx(0.00)

def test_classify_failure(client, mock_infinity_client):
    mock_infinity_client.classify.return_value = None
    result = client.classify("text", ["label"])
    assert result is None

# --- Extracted zero-shot tests from orchestrator ---

def test_evaluate_routing_success(client, monkeypatch):
    mock_classify = MagicMock(return_value={
        'Hypothesis A': 0.9,
        'Hypothesis B': 0.1
    })
    monkeypatch.setattr(client, 'classify', mock_classify)

    text = "some message"
    hipotheses = {
        'AGENT_A': 'Hypothesis A',
        'AGENT_B': 'Hypothesis B'
    }
    valid_agents = ['AGENT_A', 'AGENT_B']

    result = client.evaluate_routing(text, hipotheses, valid_agents)
    assert result == "AGENT_A"

def test_evaluate_routing_low_confidence(client, monkeypatch):
    mock_classify = MagicMock(return_value={
        'Hypothesis A': 0.005,
        'Hypothesis B': 0.005
    })
    monkeypatch.setattr(client, 'classify', mock_classify)

    text = "some message"
    hipotheses = {
        'AGENT_A': 'Hypothesis A',
        'AGENT_B': 'Hypothesis B'
    }
    valid_agents = ['AGENT_A', 'AGENT_B']

    result = client.evaluate_routing(text, hipotheses, valid_agents, confidence_threshold=0.01)
    assert result is None

def test_evaluate_routing_low_margin(client, monkeypatch):
    mock_classify = MagicMock(return_value={
        'Hypothesis A': 0.8,
        'Hypothesis B': 0.7
    })
    monkeypatch.setattr(client, 'classify', mock_classify)

    text = "some message"
    hipotheses = {
        'AGENT_A': 'Hypothesis A',
        'AGENT_B': 'Hypothesis B'
    }
    valid_agents = ['AGENT_A', 'AGENT_B']

    result = client.evaluate_routing(text, hipotheses, valid_agents, margin_threshold=0.5)
    assert result is None

def test_evaluate_routing_no_valid_agents_after_filter(client, monkeypatch):
    mock_classify = MagicMock(return_value={
        'Hypothesis A': 0.9
    })
    monkeypatch.setattr(client, 'classify', mock_classify)

    text = "some message"
    hipotheses = {
        'AGENT_A': 'Hypothesis A'
    }
    valid_agents = [] # AGENT_A is not valid

    result = client.evaluate_routing(text, hipotheses, valid_agents)
    assert result is None

