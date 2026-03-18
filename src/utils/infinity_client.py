'''InfinityClient is a simple wrapper around the
Infinity API for classification tasks.'''
import os
import requests


class InfinityClient:
    '''Client for interacting with the Infinity API for classification tasks.'''
    def __init__(self, host="http://lifeos_embeddings", port="8080"):
        self.base_url = f"{host}:{port}"
        self.api_key = os.getenv("INFINITY_API_KEY")
        if not self.api_key:
            raise ValueError("INFINITY_API_KEY environment variable not set.")

    def classify(self, input_texts: list[str],
                 model: str = "data/nli_model",
                 raw_scores: bool = False):
        '''Classify input texts using the
        Infinity API. This method sends
        a POST request to the /classify
        endpoint'''
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": model,
            "input": input_texts,
            "raw_scores": raw_scores
        }
        try:
            response = requests.post(f"{self.base_url}/classify",
                                    headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error during Infinity classification: {e}")
            return None

# Example Usage (for testing purposes, not part of the class itself)
if __name__ == "__main__":
    # Ensure INFINITY_API_KEY is set in your environment for this to work
    # export INFINITY_API_KEY="your_api_key_here"
    client = InfinityClient()
    test_texts = ["I am not having a great day."]
    result = client.classify(test_texts)
    if result:
        print("Classification Result:")
        print(result)
    else:
        print("Failed to get classification result.")
