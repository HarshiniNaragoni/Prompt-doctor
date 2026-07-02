"""
Runner module for Prompt Doctor.
Executes the student's prompt on the level's sample input using OpenRouter.
"""

import os
import json
import requests
from typing import Optional

# OpenRouter API configuration
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-4o-mini"  # Fast, capable, cost-effective judge model


def get_api_key() -> Optional[str]:
    """Get the OpenRouter API key from environment."""
    return os.getenv("OPENROUTER_API_KEY")


def run_student_prompt(
    student_prompt: str,
    sample_input: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.3
) -> dict:
    """
    Run the student's prompt on the sample input using OpenRouter.
    
    Args:
        student_prompt: The prompt written by the student.
        sample_input: The sample input for the current level.
        model: The model to use for execution.
        temperature: Temperature for generation.
    
    Returns:
        dict with keys:
            - "success": bool
            - "output": str (the model's response)
            - "error": str (if any)
    """
    api_key = get_api_key()
    if not api_key:
        return {
            "success": False,
            "output": "",
            "error": "OpenRouter API key not found. Please set OPENROUTER_API_KEY in your .env file."
        }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://prompt-doctor.app",
        "X-Title": "Prompt Doctor"
    }
    
    # Combine the student's prompt with the sample input
    messages = [
        {"role": "system", "content": student_prompt},
        {"role": "user", "content": sample_input}
    ]
    
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 2048
    }
    
    try:
        response = requests.post(
            OPENROUTER_API_URL,
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        data = response.json()
        
        if "choices" in data and len(data["choices"]) > 0:
            output = data["choices"][0]["message"]["content"]
            return {
                "success": True,
                "output": output,
                "error": ""
            }
        else:
            return {
                "success": False,
                "output": "",
                "error": f"Unexpected API response: {json.dumps(data)}"
            }
            
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "output": "",
            "error": "Request timed out after 60 seconds."
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "output": "",
            "error": f"API request failed: {str(e)}"
        }
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "output": "",
            "error": f"Failed to parse API response: {str(e)}"
        }