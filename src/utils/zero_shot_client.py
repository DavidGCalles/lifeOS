'''Zero Shot Client for NLI Classification. This layer is responsible for constructing
the premise/hypothesis pairs and routing the classification request to the InfinityClient.
It abstracts away the details of how the NLI model expects input and how to interpret the
results, providing a simple interface for zero-shot classification tasks.'''

from src.utils.infinity_client import InfinityClient
import logging
import time

logger = logging.getLogger(__name__)

class ZeroShotClient:
    '''Client for performing zero-shot classification using an NLI model via InfinityClient.'''
    def __init__(self, infinity_client: InfinityClient | None = None):
        self.client = infinity_client or InfinityClient()

    def _construct_pairs(self, text: str, labels: list[str],
                         hypothesis_template: str = "This example is {}.") -> list[str]:
        """
        Constructs the premise/hypothesis pairs for NLI classification.
        
        Args:
            text (str): The input text (premise).
            labels (list[str]): The list of candidate labels.
            hypothesis_template (str): Template for the hypothesis.
            
        Returns:
            list[str]: A list of strings formatted as 'premise [SEP] hypothesis'.
        """
        pairs = []
        for label in labels:
            hypothesis = hypothesis_template.format(label)
            # Injecting [SEP] token as requested for the NLI model input format
            pair = f"'{text} [SEP] {hypothesis}'"
            pairs.append(pair)
        return pairs

    def classify(self, text: str, labels: list[str],
                hypothesis_template: str = "I am talking to {}.") -> dict[str, float] | None:
        """
        Performs zero-shot classification by routing to
        the Infinity classification endpoint via InfinityClient.
        
        Args:
            text (str): The input text to classify.
            labels (list[str]): Candidate labels (e.g., agent names).
            hypothesis_template (str): Template to form the hypothesis.

        Returns:
            dict[str, float]: A dictionary mapping labels to their entailment scores.
                              e.g., {"finance": 0.92, "health": 0.15}
            None: If the request fails.
        """
        if not labels:
            logger.warning("ZeroShotClient: No labels provided for classification.")
            return None

        start_time = time.time()
        logger.info(f"ZeroShotClient: Classifying text against {len(labels)} labels...")

        inputs = self._construct_pairs(text, labels, hypothesis_template)
        # Use InfinityClient to classify
        response_json = self.client.classify(inputs)
        
        elapsed = time.time() - start_time
        
        if not response_json:
            logger.debug(f"ZeroShotClient: Classification failed (no response) in {elapsed:.2f}s")
            return None

        logger.info(f"ZeroShotClient: Classification completed in {elapsed:.2f}s")

        results = response_json.get("data") if isinstance(response_json, dict) else response_json
        logger.debug(f"ZeroShotClient: Raw classification results: {results}")
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
