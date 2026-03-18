'''Zero Shot Client for NLI Classification. This layer is responsible for constructing
the premise/hypothesis pairs and routing the classification request to the InfinityClient.
It abstracts away the details of how the NLI model expects input and how to interpret the
results, providing a simple interface for zero-shot classification tasks.'''
import logging
import time
import json
from src.utils.infinity_client import InfinityClient

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
            pair = f"{text} [SEP] {hypothesis}"
            pairs.append(pair)
        return pairs

    def _calculate_delta(self, item: list[dict[str, float]]) -> float:
        """
        Calculates the entailment - contradiction delta for a single classification result.
        
        Args:
            item (list[dict[str, float]]): The list of dictionaries containing scores
                                           for 'entailment', 'contradiction', and 'neutral'.
                                           
        Returns:
            float: The calculated delta score.
        """
        entailment_score = 0.0
        contradiction_score = 0.0
        if isinstance(item, list):
            for class_res in item:
                if isinstance(class_res, dict):
                    label_name = class_res.get("label")
                    if label_name == "entailment":
                        entailment_score = class_res.get("score", 0.0)
                    elif label_name == "contradiction":
                        contradiction_score = class_res.get("score", 0.0)
        return entailment_score - contradiction_score

    def classify(self, text: str, labels: list[str],
                hypothesis_template: str = "User wants to {}.",
                raw_scores: bool = False) -> dict[str, float] | None:
        """
        Performs zero-shot classification by routing to
        the Infinity classification endpoint via InfinityClient.
        
        Args:
            text (str): The input text to classify.
            labels (list[str]): Candidate labels (e.g., agent names).
            hypothesis_template (str): Template to form the hypothesis.
            raw_scores (bool): Whether to return raw logits instead of probabilities.

        Returns:
            dict[str, float]: A dictionary mapping labels to their entailment - contradiction delta scores.
                              e.g., {"finance": 0.92, "health": -0.15}
            None: If the request fails.
        """
        if not labels:
            logger.warning("ZeroShotClient: No labels provided for classification.")
            return None

        start_time = time.time()
        logger.info("ZeroShotClient: Classifying text against %d labels...", len(labels))

        inputs = self._construct_pairs(text, labels, hypothesis_template)
        # Use InfinityClient to classify
        response_json = self.client.classify(inputs, raw_scores=raw_scores)
        elapsed = time.time() - start_time
        if not response_json:
            logger.debug("ZeroShotClient: Classification failed (no response) in %.2f}s", elapsed)
            return None

        logger.info("ZeroShotClient: Infinity Classification completed in %.2f s", elapsed)

        results = response_json.get("data") if isinstance(response_json, dict) else response_json
        if not isinstance(results, list):
            return None

        scores = {}

        for i, item in enumerate(results):
            if i >= len(labels):
                break
            scores[labels[i]] = self._calculate_delta(item)
        logger.debug("ZeroShotClient: Calculated delta scores: %s", scores)
        return scores

    def _check_margin(self, top_score: float, second_score: float, margin_threshold: float) -> bool:
        """
        Checks if the absolute margin between the top and second score
        meets the required threshold.
        """
        margin = top_score - second_score
        if margin < margin_threshold:
            logger.info("⚠️ Zero-Shot Margin too low: %.2f vs %.2f (margin: %.2f)",
                        top_score, second_score, margin)
            return False
        return True

    def evaluate_routing(
        self,
        text: str,
        hipotheses: dict[str, str],
        valid_agents: list[str],
        confidence_threshold: float = 0.01,
        margin_threshold: float = 0.5
    ) -> str | None:
        """
        Evaluates the best agent for a given text based on zero-shot classification.
        Applies confidence thresholds and margin checks directly on the delta scores.

        Args:
            text (str): The input text to route.
            hipotheses (dict[str, str]): Mapping of agent_key -> hypothesis text.
            valid_agents (list[str]): List of valid agent keys in the configuration.
            confidence_threshold (float): Minimum delta score required to route.
            margin_threshold (float): Minimum difference between top 1 and top 2 agents.

        Returns:
            str | None: The key of the selected agent (uppercase), or None if it fails
                        to meet the confidence/margin thresholds.
        """
        start_time = time.time()
        
        # Create reverse mapping: hypothesis text -> agent key
        hypothesis_to_agent = {v: k for k, v in hipotheses.items()}
        
        # Run classification
        scores = self.classify(text, list(hipotheses.values()))
        if not scores:
            logger.warning("⚠️ Zero-Shot returned no scores.")
            return None

        # Filter scores to only valid agents and capture max raw score
        valid_scores = {}
        for hypothesis, score in scores.items():
            agent_key = hypothesis_to_agent.get(hypothesis)
            if agent_key and agent_key in valid_agents:
                valid_scores[hypothesis] = score
                
        scores = valid_scores
        if not scores:
            logger.info("ℹ️ Zero-Shot: No valid agent matches found after filtering.")
            return None

        # Sort scores descending
        sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)

        # Relate back to agent keys using the reverse mapping
        mapped_scores = []
        for hypothesis, score in sorted_scores:
            agent_key = hypothesis_to_agent.get(hypothesis)
            mapped_scores.append((agent_key, score))
        sorted_scores = mapped_scores
        
        # Log all probabilities
        logger.info("📊 Zero-Shot Probabilities: %s", json.dumps(sorted_scores))
        
        if not sorted_scores:
            logger.info("ℹ️ Zero-Shot: No valid agent matches found.")
            return None
            
        top_agent, top_score = sorted_scores[0]
        
        #Confidence check
        confidence_pass = False
        if top_score > confidence_threshold:
            confidence_pass = True
        else:
            logger.info(
                "⚠️ Zero-Shot Confidence too low: %.2f (threshold: %.2f). Fallback to Router.",
                top_score, confidence_threshold)

        # Margin check (Threshold between top 1 and top 2)
        margin_pass = False
        if len(sorted_scores) > 1:
            second_score = sorted_scores[1][1]
            margin_pass = self._check_margin(top_score, second_score, margin_threshold)
                            
        if confidence_pass and margin_pass:
            elapsed = time.time() - start_time
            logger.info(
                "⚡ Zero-Shot Selected: %s (delta=%.2f) in %.2fs",
                top_agent.upper(), top_score, elapsed)
            return top_agent.upper()
        return None
