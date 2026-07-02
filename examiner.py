"""
Examiner module for Prompt Doctor.
This is the heart of the application — a prompt that grades prompts.
YOU BUILD THIS: the examiner prompt + the grading call.
"""

import os
import json
import requests
import re
from typing import Optional

from levels import get_level, get_principles_for_level
from runner import DEFAULT_MODEL

# OpenRouter configuration
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
EXAMINER_MODEL = "openai/gpt-4o"  # Capable model for consistent grading


EXAMINER_SYSTEM_TEMPLATE = """
You are the Examiner: a strict but fair prompt-engineering assessor.

You will be given:
1. A LEVEL number (1-5)
2. The PRINCIPLES that must be judged for this level
3. A STUDENT_PROMPT written by a learner
4. The SAMPLE_INPUT the prompt was supposed to handle
5. The LIVE_OUTPUT produced by running the student's prompt on the sample input

Grade STUDENT_PROMPT for LEVEL {level}. Judge ONLY these principles:

{principles_for_this_level}

Obey these rules:
1. Judge against the principles in your OWN words — be specific. Do not just restate the principle; explain how the prompt does or does not satisfy it.
2. For each failed principle, quote the exact weak phrase (or name what's missing) from the student's prompt.
3. Ask ONE pointed question that leads to the fix for each failed principle.
4. NEVER write, rewrite, or give an example of a corrected prompt. Diagnose only.
5. Reason step by step inside <reasoning> tags, THEN output ONLY the JSON verdict.
6. The JSON verdict must be valid parsable JSON with no markdown wrapping, no code fences.

Your JSON verdict must use this exact schema:
{{
  "level": {level},
  "principles": [
    {{
      "name": "principle_name",
      "pass": true or false,
      "weakness": "If failed, quote the exact weak phrase or describe what's missing. If passed, leave empty string.",
      "question": "If failed, one pointed question that leads to the fix. If passed, leave empty string."
    }}
  ],
  "ran_ok": true,
  "verdict": "pass" or "revise"
}}

The verdict is "pass" ONLY when every principle passes. Otherwise it's "revise".
"""


def get_api_key() -> Optional[str]:
    """Get the OpenRouter API key from environment."""
    return os.getenv("OPENROUTER_API_KEY")


def extract_json_from_response(text: str) -> Optional[dict]:
    """
    Extract JSON from the examiner's response.
    Handles cases where the model wraps JSON in markdown code blocks
    or includes extra text.
    """
    # Try to find JSON within code blocks first
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if json_match:
        json_str = json_match.group(1).strip()
    else:
        # Try to find JSON object directly
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            json_str = json_match.group(0)
        else:
            return None
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def grade_prompt(
    student_prompt: str,
    sample_input: str,
    live_output: str,
    level: int,
    model: str = EXAMINER_MODEL
) -> dict:
    """
    Grade a student's prompt using the examiner LLM.
    
    Args:
        student_prompt: The prompt written by the student.
        sample_input: The sample input for the current level.
        live_output: The output produced by running the student's prompt.
        level: The current level number.
        model: The model to use for grading.
    
    Returns:
        dict with keys:
            - "success": bool
            - "verdict": dict (the parsed JSON verdict) or None
            - "raw_response": str (the raw response from the examiner)
            - "error": str (if any)
    """
    api_key = get_api_key()
    if not api_key:
        return {
            "success": False,
            "verdict": None,
            "raw_response": "",
            "error": "OpenRouter API key not found. Please set OPENROUTER_API_KEY in your .env file."
        }
    
    principles_text = get_principles_for_level(level)
    if not principles_text:
        return {
            "success": False,
            "verdict": None,
            "raw_response": "",
            "error": f"Level {level} not found."
        }
    
    system_prompt = EXAMINER_SYSTEM_TEMPLATE.format(
        level=level,
        principles_for_this_level=principles_text
    )
    
    user_message = f"""LEVEL: {level}

STUDENT_PROMPT:
{student_prompt}

SAMPLE_INPUT:
{sample_input}

LIVE_OUTPUT (produced by running the student's prompt on the sample input):
{live_output}

Grade this student prompt against the principles for Level {level}. Remember: reason step by step, then output ONLY the JSON verdict."""
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://prompt-doctor.app",
        "X-Title": "Prompt Doctor"
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.1,  # Low temperature for consistent grading
        "max_tokens": 2048
    }
    
    try:
        response = requests.post(
            OPENROUTER_API_URL,
            headers=headers,
            json=payload,
            timeout=90  # Longer timeout for the reasoning step
        )
        response.raise_for_status()
        data = response.json()
        
        if "choices" in data and len(data["choices"]) > 0:
            raw = data["choices"][0]["message"]["content"]
            
            # Parse the JSON verdict from the response
            verdict = extract_json_from_response(raw)
            
            if verdict:
                # Validate the verdict structure
                if "principles" in verdict and "verdict" in verdict:
                    return {
                        "success": True,
                        "verdict": verdict,
                        "raw_response": raw,
                        "error": ""
                    }
                else:
                    return {
                        "success": False,
                        "verdict": None,
                        "raw_response": raw,
                        "error": "Verdict missing required fields (principles, verdict)."
                    }
            else:
                return {
                    "success": False,
                    "verdict": None,
                    "raw_response": raw,
                    "error": "Failed to parse JSON verdict from examiner response."
                }
        else:
            return {
                "success": False,
                "verdict": None,
                "raw_response": "",
                "error": f"Unexpected API response: {json.dumps(data)}"
            }
            
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "verdict": None,
            "raw_response": "",
            "error": "Examiner request timed out after 90 seconds."
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "verdict": None,
            "raw_response": "",
            "error": f"Examiner API request failed: {str(e)}"
        }
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "verdict": None,
            "raw_response": "",
            "error": f"Failed to parse examiner API response: {str(e)}"
        }


def build_fallback_verdict(level: int, error_msg: str) -> dict:
    """
    Build a fallback verdict when the examiner fails.
    This allows the app to still function and show an error state.
    """
    level_def = get_level(level)
    if not level_def:
        return {
            "level": level,
            "principles": [],
            "ran_ok": False,
            "verdict": "revise"
        }
    
    principles = []
    for p in level_def["principles"]:
        principles.append({
            "name": p,
            "pass": False,
            "weakness": f"Examiner error: {error_msg}",
            "question": "Please try again. If the issue persists, check your API key and internet connection."
        })
    
    return {
        "level": level,
        "principles": principles,
        "ran_ok": False,
        "verdict": "revise"
    }