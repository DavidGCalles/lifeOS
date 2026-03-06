import unittest
from unittest.mock import MagicMock
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.zero_shot_client import ZeroShotClient

class TestZeroShotClient(unittest.TestCase):
    def setUp(self):
        self.mock_infinity_client = MagicMock()
        self.client = ZeroShotClient(infinity_client=self.mock_infinity_client)

    def test_construct_pairs(self):
        text = "Hello world"
        labels = ["greeting", "farewell"]
        expected = [
            "Hello world [SEP] This example is greeting.",
            "Hello world [SEP] This example is farewell."
        ]
        pairs = self.client._construct_pairs(text, labels)
        self.assertEqual(pairs, expected)

    def test_construct_pairs_custom_template(self):
        text = "Hello"
        labels = ["A"]
        template = "Category: {}"
        expected = ["Hello [SEP] Category: A"]
        pairs = self.client._construct_pairs(text, labels, hypothesis_template=template)
        self.assertEqual(pairs, expected)

    def test_classify_success(self):
        # Mock response from InfinityClient
        # Input: 2 labels. 
        # Label 1 (finance): entailment 0.95
        # Label 2 (health): entailment 0.10
        
        self.mock_infinity_client.classify.return_value = {
            "data": [
                [
                    {"label": "entailment", "score": 0.95},
                    {"label": "neutral", "score": 0.05},
                    {"label": "contradiction", "score": 0.0}
                ],
                [
                    {"label": "entailment", "score": 0.10},
                    {"label": "neutral", "score": 0.80},
                    {"label": "contradiction", "score": 0.10}
                ]
            ]
        }

        text = "Invest in stocks"
        labels = ["finance", "health"]
        
        result = self.client.classify(text, labels)
        
        self.assertIsNotNone(result)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["finance"], 0.95)
        self.assertEqual(result["health"], 0.10)

        # Verify InfinityClient.classify was called with correct inputs
        expected_inputs = [
            "Invest in stocks [SEP] I am talking to finance.",
            "Invest in stocks [SEP] I am talking to health."
        ]
        self.mock_infinity_client.classify.assert_called_once_with(expected_inputs, raw_scores=False)

    def test_classify_empty_labels(self):
        result = self.client.classify("text", [])
        self.assertIsNone(result)
        self.mock_infinity_client.classify.assert_not_called()

    def test_classify_failure(self):
        self.mock_infinity_client.classify.return_value = None
        result = self.client.classify("text", ["label"])
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
