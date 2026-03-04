import requests
import os

class InfinityClient:
    def __init__(self, host="http://localhost", port="8080"):
        self.base_url = f"{host}:{port}"
        self.api_key = os.getenv("INFINITY_API_KEY")
        if not self.api_key:
            raise ValueError("INFINITY_API_KEY environment variable not set.")

    def classify(self, text: str, candidate_labels: list[str]):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "text": text,
            "candidate_labels": candidate_labels
        }
        try:
            response = requests.post(f"{self.base_url}/classify", headers=headers, json=payload)
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
    
    test_text = "I want to add milk to my grocery list."
    test_labels = ["add_grocery", "set_reminder", "general_chat"]
    
    result = client.classify(test_text, test_labels)
    
    if result:
        print("Classification Result:")
        print(result)
    else:
        print("Failed to get classification result.")
