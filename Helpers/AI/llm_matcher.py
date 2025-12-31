import requests
import json
import os

class SemanticMatcher:
    def __init__(self, model='qwen3-vl:2b-custom'):
        # The model name doesn't strictly matter for the raw server as it only serves one model,
        # but we keep it for compatibility with the signature.
        self.model = model
        self.api_url = os.getenv("LLM_API_URL", "http://127.0.0.1:8080/v1/chat/completions")

    def is_match(self, team1, team2, league=None):
        """
        Determines if two team names refer to the same entity using the local llama-server.
        """
        context = ""
        if league:
            context = f"They play in the league: {league}."
            
        prompt = (
            f"Are the sports teams '{team1}' and '{team2}' the same team? "
            f"{context} "
            "Answer with exactly one word: 'Yes' or 'No'."
        )
        
        payload = {
            "model": self.model, # Passed but ignored by single-model server
            "messages": [
                {'role': 'user', 'content': prompt}
            ],
            "temperature": 0.0,
            "max_tokens": 10
        }

        try:
            response = requests.post(self.api_url, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            # Handle standard OpenAI-compatible response structure
            ans = data['choices'][0]['message']['content'].strip().lower()
            return 'yes' in ans
            
        except Exception as e:
            print(f"  [LLM Error] Failed to match {team1} vs {team2}: {e}")
            return False
