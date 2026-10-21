import os
from backend.llm.client import LLMClient
from backend.llm.prompts import FIX_PROMPT_TEMPLATE

def generate_fix(finding: dict, target_dir: str) -> str:
    llm = LLMClient()
    rel_filename = finding.get("filename", "")
    if os.path.isabs(rel_filename):
        file_path = rel_filename
    else:
        file_path = os.path.join(target_dir, rel_filename)

    code_snippet = ""
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            code_snippet = f.read()

    prompt = FIX_PROMPT_TEMPLATE.format(
        rule_id=finding.get("test_id", "UNKNOWN"),
        issue_text=finding.get("issue_text", ""),
        file_path=finding.get("filename", ""),
        line_number=finding.get("line_number", 1),
        code_snippet=code_snippet
    )

    response = llm.query(prompt)
    return response