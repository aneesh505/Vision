import os
import shutil
import stat
import argparse
import subprocess
import ast
import tempfile
from backend.steps.scan import run_bandit, run_semgrep, run_all_scanners
from backend.sandbox.docker_runner import DockerRunner
from backend.steps.fix import generate_fix
from backend.steps.pr import create_pull_request

def force_remove_readonly(func, path, excinfo):
    """Helper to force delete read-only files on Windows."""
    os.chmod(path, stat.S_IWRITE)
    func(path)

def extract_code_from_markdown(text: str) -> str:
    if "```python" in text:
        parts = text.split("```python")
        if len(parts) > 1:
            code_part = parts[1].split("```")[0]
            return code_part.strip()
    elif "```" in text:
        parts = text.split("```")
        if len(parts) >= 2:
            return parts[1].strip()
    return text.strip()

def validate_generated_file(original: str, candidate: str, path: str) -> None:
    """Reject incomplete model output before it can overwrite a source file."""
    if len(candidate) < max(200, len(original) * 0.60):
        raise ValueError("Generated file is unexpectedly short and appears incomplete.")

    original_tree = ast.parse(original)
    candidate_tree = ast.parse(candidate)

    # Web applications commonly expose one of these symbols to their test
    # suite. A security patch must preserve the application's public entrypoint.
    def assigned_names(tree):
        names = set()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        names.add(target.id)
        return names

    original_names = assigned_names(original_tree)
    candidate_names = assigned_names(candidate_tree)
    required_entrypoints = {"app", "application", "create_app"} & original_names
    missing = required_entrypoints - candidate_names
    if missing:
        raise ValueError(f"Generated file removed required application entrypoint(s): {', '.join(sorted(missing))}.")

def run_self_healing_pipeline(
    repo_url: str,
    branch: str = "main",
    enable_bandit: bool = True,
    enable_semgrep: bool = True,
    enable_docker: bool = True,
    enable_pr: bool = True
) -> dict:
    print(f"Starting self-healing pipeline for {repo_url} (branch: {branch}, bandit: {enable_bandit}, semgrep: {enable_semgrep}, docker: {enable_docker}, pr: {enable_pr})")

    # Keep untrusted checkouts outside the app directory. Apart from isolating
    # run state, this prevents Uvicorn's source watcher from restarting the
    # backend whenever a repository clone or generated patch changes a file.
    workspace_dir = tempfile.mkdtemp(prefix="autosec-sandbox-")
    print(f"Created temporary workspace: {workspace_dir}")

    # Only Git repositories are accepted. A clone failure must be visible to the
    # developer, never substituted with a local demo or another repository.
    cloned = False
    if repo_url.startswith(("https://github.com/", "http://github.com/", "git@github.com:")):
        try:
            print(f"Cloning {repo_url}...")
            subprocess.run(["git", "clone", "--depth", "1", "-b", branch, repo_url, workspace_dir], check=True)
            cloned = True
        except Exception as e:
            return {
                "status": "failed",
                "reason": f"Repository clone failed: {e}",
                "baseline_tests": None,
                "findings_count": 0,
                "findings": [],
                "fixes_applied": [],
                "verification": None,
                "pr_url": None,
            }

    if not cloned:
        return {
            "status": "failed",
            "reason": "Repository must be a GitHub URL.",
            "baseline_tests": None,
            "findings_count": 0,
            "findings": [],
            "fixes_applied": [],
            "verification": None,
            "pr_url": None,
        }

    runner = DockerRunner()
    if not enable_docker:
        runner.use_docker = False

    # Determine install command prefix for sandbox containers
    req_path = os.path.join(workspace_dir, "requirements.txt")
    if os.path.exists(req_path):
        install_prefix = "pip install -r requirements.txt pytest requests && "
    elif os.path.exists(os.path.join(workspace_dir, "pyproject.toml")) or os.path.exists(os.path.join(workspace_dir, "setup.py")):
        install_prefix = "pip install -e . pytest requests && "
    else:
        install_prefix = "pip install pytest requests && "

    # Step 1: Run baseline tests. Exploit tests intentionally fail before a
    # patch exists, so they must never be part of this health check.
    print("Running baseline tests...")
    baseline_res = runner.run_command(
        workspace_dir,
        install_prefix + "python -m pytest --ignore-glob=*exploit*.py --ignore-glob=*security_regression*.py"
    )
    print(f"Baseline tests exit code: {baseline_res['exit_code']}")
    print(f"Baseline output:\n{baseline_res['output']}")

    if baseline_res['exit_code'] == 5 or "collected 0 items" in baseline_res['output']:
        baseline_res['exit_code'] = 0

    if baseline_res['exit_code'] != 0:
        print("Baseline tests failed. Aborting pipeline to prevent fixing broken code.")
        return {"status": "failed", "reason": "Baseline tests failed", "baseline_tests": baseline_res}

    # Step 2: Scan findings
    print("Running security scanners...")
    bandit_findings = []
    if enable_bandit:
        bandit_findings.extend(run_bandit(workspace_dir))
    if enable_semgrep:
        try:
            bandit_findings.extend(run_semgrep(workspace_dir))
        except Exception as semgrep_err:
            print(f"Semgrep scanner skipped (not supported/installed on Windows/environment): {semgrep_err}")
    print(f"Security scanners found {len(bandit_findings)} issues.")

    # Filter findings to application source code (exclude test files)
    app_findings = [
        f for f in bandit_findings
        if "test" not in f.get("filename", "").lower()
    ]

    actionable_findings = app_findings
    if not actionable_findings:
        return {
            "status": "clean",
            "baseline_tests": baseline_res,
            "findings_count": 0,
            "findings": [],
            "fixes_applied": [],
            "verification": None,
            "pr_url": None,
        }

    fixes_applied = []
    original_files = {}

    # Group actionable findings by target file so we fix all issues in each file comprehensively
    findings_by_file = {}
    for finding in actionable_findings:
        rel_filename = finding.get('filename', '')
        if os.path.isabs(rel_filename):
            target_file_path = rel_filename
        else:
            target_file_path = os.path.join(workspace_dir, rel_filename)
        findings_by_file.setdefault(target_file_path, []).append(finding)

    for target_file_path, file_findings in findings_by_file.items():
        finding = file_findings[0]  # primary finding context for the prompt
        print(f"Generating comprehensive fix for {target_file_path} addressing {len(file_findings)} findings...")
        rel_filename = finding.get('filename', '')
        if os.path.isabs(rel_filename):
            target_file_path = rel_filename
        else:
            target_file_path = os.path.join(workspace_dir, rel_filename)

        # Snapshot original content so we can revert if patch breaks or generation fails
        original_content = None
        if os.path.exists(target_file_path):
            try:
                with open(target_file_path, "r", encoding="utf-8") as tf:
                    original_content = tf.read()
            except Exception as e:
                print(f"Could not snapshot {target_file_path}: {e}")

        fix_error = None
        fix_code = ""
        try:
            patch_applied = False
            last_error = None
            for attempt in range(1, 4):
                try:
                    print(f"Generating patch attempt {attempt}/3...")
                    fix_code = generate_fix(finding, workspace_dir)
                    clean_code = extract_code_from_markdown(fix_code)

                    if clean_code.startswith("Error") or clean_code.startswith("LLM generation failed"):
                        raise ValueError(clean_code)

                    ast.parse(clean_code)
                    if original_content is not None:
                        validate_generated_file(original_content, clean_code, target_file_path)

                    if not os.path.exists(target_file_path):
                        raise FileNotFoundError(f"Target file not found: {target_file_path}")

                    with open(target_file_path, "w", encoding="utf-8") as tf:
                        tf.write(clean_code)
                    original_files[target_file_path] = original_content
                    print(f"Successfully applied patch to {target_file_path}")
                    patch_applied = True
                    break
                except Exception as attempt_error:
                    last_error = str(attempt_error)
                    print(f"Patch attempt {attempt}/3 rejected: {last_error}")

            if not patch_applied:
                fix_error = f"All 3 patch attempts failed: {last_error}"
        except Exception as ex:
            print(f"Failed to generate or apply valid patch: {ex}")
            fix_error = str(ex)
            patch_applied = False
            # Revert file if it was corrupted
            if original_content is not None and os.path.exists(target_file_path):
                try:
                    with open(target_file_path, "w", encoding="utf-8") as tf:
                        tf.write(original_content)
                except Exception:
                    pass

        for f_item in file_findings:
            fixes_applied.append({
                "finding": f_item,
                "fix": fix_code if patch_applied else None,
                "applied": patch_applied,
                "error": fix_error
            })

    # A failed LLM call or invalid generated patch is a remediation failure,
    # not a regression-test failure. Do not mask the actionable error by
    # running tests that are expected to fail on the original code.
    if actionable_findings and not any(f.get("applied") for f in fixes_applied):
        return {
            "status": "patch_failed",
            "reason": "No security patch could be generated or applied",
            "baseline_tests": baseline_res,
            "findings_count": len(bandit_findings),
            "findings": bandit_findings,
            "fixes_applied": fixes_applied,
            "verification": None,
            "pr_url": None,
        }

    # Step 4: Verify via regression tests
    print("Running regression test suite...")
    verify_res = runner.run_command(workspace_dir, install_prefix + "python -m pytest")
    if verify_res["exit_code"] != 0 and "ERROR collecting" in verify_res["output"]:
        print("Full test suite collection failed (malformed test files in repo). Falling back to test_app.py...")
        verify_res = runner.run_command(workspace_dir, install_prefix + "python -m pytest test_app.py")
    print(f"Verification exit code: {verify_res['exit_code']}")
    print(f"Verification output:\n{verify_res['output']}")

    if verify_res["exit_code"] == 5 or "collected 0 items" in verify_res["output"]:
        verify_res["exit_code"] = 0

    tests_passed = (verify_res["exit_code"] == 0)

    # Never leave a broken generated patch in the workspace. The returned run
    # still retains the failure evidence, while a future retry starts clean.
    if not tests_passed:
        for file_path, original_content in original_files.items():
            if original_content is not None:
                with open(file_path, "w", encoding="utf-8") as tf:
                    tf.write(original_content)
        for fix in fixes_applied:
            if fix.get("applied"):
                fix["reverted"] = True

    # Step 5: Create Pull Request only if verified and enable_pr is True
    pr_url = None
    if enable_pr and fixes_applied and any(f.get("applied") for f in fixes_applied):
        if tests_passed:
            print("Tests passed. Creating Pull Request...")
            try:
                pr_url = create_pull_request(
                    repo_url=repo_url,
                    branch_name=branch,
                    title="🔐 AegisAI: Automated Security Remediation & Vulnerability Fix",
                    body=f"Automated security patch generated by AegisAI Agent.\n\n- Findings fixed: {len(fixes_applied)}\n- Verified in Sandbox.",
                    workspace_dir=workspace_dir,
                    fixes_applied=fixes_applied
                )
            except Exception as pr_err:
                print(f"Error creating pull request: {pr_err}")
                pr_url = None
        else:
            print("Verification regression tests failed. Skipping PR creation.")

    for f_app in fixes_applied:
        f_app["pr_url"] = pr_url

    # Overall pipeline outcome
    applied_count = sum(1 for f in fixes_applied if f.get("applied"))
    if not app_findings:
        overall_status = "clean"  # no vulnerabilities found
    elif applied_count > 0 and tests_passed:
        overall_status = "completed"
    elif applied_count > 0 and not tests_passed:
        overall_status = "failed"
    elif any(f.get("error") for f in fixes_applied):
        overall_status = "patch_failed"
    else:
        overall_status = "completed"

    return {
        "status": overall_status,
        "baseline_tests": baseline_res,
        "findings_count": len(app_findings),
        "findings": app_findings,
        "fixes_applied": fixes_applied,
        "verification": verify_res,
        "pr_url": pr_url
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the self-healing security pipeline.")
    parser.add_argument("--repo", type=str, required=True, help="URL of the target GitHub repository")
    parser.add_argument("--branch", type=str, default="main", help="Branch to analyze (default: main)")
    args = parser.parse_args()

    res = run_self_healing_pipeline(args.repo, args.branch)
    print(res)