FIX_PROMPT_TEMPLATE = """
You are an expert security engineer. You have been given a vulnerable Python file identified by static analysis tools (Bandit/Semgrep).

VULNERABILITY DETAILS:
- Rule ID: {rule_id}
- Issue: {issue_text}
- File: {file_path}
- Line: {line_number}

FULL FILE CONTENT:
```python
{code_snippet}
```

TASK:
Provide a secure, robust, defense-in-depth code fix that eliminates the vulnerability without breaking existing functionality. Return ONLY the ENTIRE updated Python file content enclosed in ```python ... ``` code blocks. Do not omit any functions or imports.

HARD REQUIREMENTS:
- Preserve every existing route, public function, and application entrypoint.
- Include all imports needed by the unchanged code (for HTML escaping, use `from markupsafe import escape`, not `from flask import escape`).
- Do not return a diff, an explanation, or a partial code snippet.
- Continue until the closing code fence only after the complete file is present.
"""

EXPLOIT_PROMPT_TEMPLATE = """
You are an expert offensive security engineer. Write a pytest test case that proves the following vulnerability exists.

VULNERABILITY:
- Type: {rule_id}
- Issue: {issue_text}
- File: {file_path}

Write a standalone pytest test function (e.g. `test_exploit_{rule_id}`) that sends a malicious payload (like SQL injection or command injection) to the app and asserts that the vulnerability is exploitable (e.g., receives 200 OK with leaked data instead of 401/400).
Return ONLY executable python pytest code.
"""