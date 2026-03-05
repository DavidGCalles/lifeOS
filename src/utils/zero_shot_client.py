from typing import List, Dict, Any, Optional
from src.utils.infinity_client import InfinityClient

class ZeroShotClient:
    def __init__(self, infinity_client: Optional[InfinityClient] = None):
        self.client = infinity_client or InfinityClient()

    def _construct_pairs(self, text: str, labels: List[str], hypothesis_template: str = "This example is {}.") -> List[str]:
        """
        Constructs the premise/hypothesis pairs for NLI classification.
        
        Args:
            text (str): The input text (premise).
            labels (List[str]): The list of candidate labels.
            hypothesis_template (str): Template for the hypothesis.
            
        Returns:
            List[str]: A list of strings formatted as 'premise [SEP] hypothesis'.
        """
        pairs = []
        for label in labels:
            hypothesis = hypothesis_template.format(label)
            # Injecting [SEP] token as requested for the NLI model input format
            pair = f"{text} [SEP] {hypothesis}"
            pairs.append(pair)
        return pairs

    def classify(self, text: str, labels: List[str], hypothesis_template: str = "This example is {}.") -> Optional[Dict[str, float]]:
        """
        Performs zero-shot classification by routing to the Infinity classification endpoint via InfinityClient.
        
        Args:
            text (str): The input text to classify.
            labels (List[str]): Candidate labels (e.g., agent names).
            hypothesis_template (str): Template to form the hypothesis.

        Returns:
            Dict[str, float]: A dictionary mapping labels to their entailment scores.
                              e.g., {"finance": 0.92, "health": 0.15}
            None: If the request fails.
        """
        if not labels:
            return None

        inputs = self._construct_pairs(text, labels, hypothesis_template)
        
        # Use InfinityClient to classify
        response_json = self.client.classify(inputs)
        
        if not response_json:
            return None

        results = response_json.get("results") if isinstance(response_json, dict) else response_json
        
        if not isinstance(results, list):
            return None

        scores = {}

        for i, item in enumerate(results):
            if i >= len(labels):
                break
            
            entailment_score = 0.0
            if isinstance(item, list):
                for class_res in item:
                    if isinstance(class_res, dict) and class_res.get("label") == "entailment":
                        entailment_score = class_res.get("score", 0.0)
                        break
            
            scores[labels[i]] = entailment_score

        return scores