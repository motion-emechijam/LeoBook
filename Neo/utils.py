"""
Neo Utils Module
Utility functions for the Neo package.
"""

import re


def clean_json_response(text: str) -> str:
    """
    Cleans Gemini response to ensure valid JSON parsing.
    Removes Markdown fences and attempts to fix common escape issues.
    """
    if not text:
        return "{}"

    # 1. Remove Markdown code blocks
    text = re.sub(r"^```json\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^```\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"```$", "", text, flags=re.MULTILINE)

    # 2. Remove any remaining markdown formatting
    text = re.sub(r"^```\w*\s*", "", text, flags=re.MULTILINE)

    # 3. Handle truncated JSON first (before other processing)
    text = text.strip()
    if text.count('{') > text.count('}') and not text.endswith('}'):
        # Try to close the JSON if it's incomplete
        brace_count = text.count('{') - text.count('}')
        if brace_count > 0:
            text += '}' * brace_count

    # 4. Fix malformed escape sequences more aggressively
    # Replace any backslash that's not followed by valid JSON escape chars
    text = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", text)

    # 5. Handle unescaped quotes within strings (very common Gemini issue)
    # Look for patterns like "selector": "div.class[attr="value"]"
    # and escape the inner quotes
    text = re.sub(r'("selector"\s*:\s*"[^"]*)"([^"]*)"([^"]*")', lambda m: m.group(1) + m.group(2).replace('"', '\\"') + m.group(3), text)

    # 6. Fix incomplete strings that might cause parsing issues
    # Find strings that start but don't end properly
    lines = text.split('\n')
    for i, line in enumerate(lines):
        # Check for lines that have opening quote but no closing quote
        if '"' in line and line.count('"') % 2 == 1:
            # If it ends with a colon or comma, it might be incomplete
            if line.strip().endswith((':',';')):
                # Try to close the string
                if not line.strip().endswith('",'):
                    lines[i] = line.rstrip() + ' "",'
                break

    text = '\n'.join(lines)

    # 7. Ensure we have at least basic JSON structure
    text = text.strip()
    if not text.startswith('{') and not text.startswith('['):
        # If it doesn't start with JSON markers, wrap it
        text = f'{{"response": "{text.replace(chr(34), chr(92) + chr(34))}"}}'

    # 8. Final cleanup - remove any remaining problematic characters
    # Remove null bytes and other control characters that might break JSON
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)

    # 9. Validate JSON structure one more time
    brace_count = text.count('{') - text.count('}')
    bracket_count = text.count('[') - text.count(']')

    if brace_count > 0:
        text += '}' * brace_count
    if bracket_count > 0:
        text += ']' * bracket_count

    return text
