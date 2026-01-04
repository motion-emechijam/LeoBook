# api_key_manager.py
import os
import requests
import json
import base64

# Default fallback URL if env var is missing
DEFAULT_API_URL = "http://127.0.0.1:8080/v1/chat/completions"

import asyncio

async def gemini_api_call_with_rotation(prompt_content, generation_config=None, **kwargs):
    """
    Redirects legacy Gemini calls to our local compatible AI server (llama-server/Qwen3-VL).
    Uses asyncio.to_thread to keep the event loop running during the blocking request.
    """
    api_url = os.getenv("LLM_API_URL", DEFAULT_API_URL)

    # 1. Parse Input (Text + Images)
    message_content = []

    if isinstance(prompt_content, list):
        for item in prompt_content:
            if isinstance(item, str):
                message_content.append({"type": "text", "text": item})
            elif isinstance(item, dict) and "inline_data" in item:
                # Extract image data
                b64_data = item["inline_data"].get("data")
                if b64_data:
                    message_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{b64_data}"
                        }
                    })
    elif isinstance(prompt_content, str):
        message_content.append({"type": "text", "text": prompt_content})

    # 2. Parse Config (Temperature)
    temperature = 0.1
    if generation_config:
        if hasattr(generation_config, 'temperature'):
            temperature = generation_config.temperature
        elif isinstance(generation_config, dict) and 'temperature' in generation_config:
            temperature = generation_config['temperature']

    # 3. Construct Payload
    payload = {
        "model": "qwen2-vl", # Explicitly add model key
        "messages": [
            {
                "role": "user",
                "content": message_content if isinstance(prompt_content, list) else prompt_content
            }
        ],
        "temperature": temperature,
        "max_tokens": 1500, # More conservative to avoid context overflow
        "stream": False
    }

    # Note: 'response_format' is removed to avoid 400 errors.

    # 4. Execute with Retry for 503 (Loading Model)
    max_retries = 12
    retry_delay = 10 # seconds

    for attempt in range(max_retries):
        try:
            def _make_request():
                return requests.post(api_url, json=payload, timeout=180)

            response = await asyncio.to_thread(_make_request)
            
            if response.status_code == 503:
                print(f"    [AI Bridge] Server is loading model (503). Retrying in {retry_delay}s... ({attempt+1}/{max_retries})")
                await asyncio.sleep(retry_delay)
                continue

            response.raise_for_status()
            
            data = response.json()
            ans = data['choices'][0]['message']['content']

            # Wrap response to match Mock Gemini object interface
            class MockGeminiResponse:
                def __init__(self, content):
                    self.text = content
                    self.candidates = [
                        type('MockCandidate', (), {
                            'content': type('MockContent', (), {
                                'parts': [type('MockPart', (), {'text': content})]
                            })
                        })
                    ]

            return MockGeminiResponse(ans)

        except Exception as e:
            # Handle non-503 errors or final failure
            error_msg = str(e)
            if 'response' in locals() and hasattr(response, 'text'):
                error_msg += f" | Server Response: {response.text}"
            print(f"    [AI Bridge Error] Failed to connect to {api_url}: {error_msg}")
            return None
    
    print(f"    [AI Bridge Error] AI Server timed out after {max_retries * retry_delay}s of loading.")
    return None
