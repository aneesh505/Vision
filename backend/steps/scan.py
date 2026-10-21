import subprocess
import json
import os
import tempfile

def run_bandit(target_dir: str) -> list:
    """Runs Bandit on the target directory and returns findings without cluttering the repo."""
    fd, output_file = tempfile.mkstemp(suffix=".json", prefix="bandit_")
    os.close(fd)
    results = []
    try:
        subprocess.run(
            ["bandit", "-r", target_dir, "-f", "json", "-o", output_file],
            capture_output=True,
            text=True,
            check=False
        )
        if os.path.exists(output_file):
            with open(output_file, "r") as f:
                data = json.load(f)
                bandit_results = data.get("results", [])
                norm_target = os.path.abspath(target_dir)
                for r in bandit_results:
                    fn = r.get("filename", "")
                    if fn and os.path.isabs(fn):
                        try:
                            fn = os.path.relpath(fn, norm_target)
                        except ValueError:
                            pass
                    results.append({
                        "test_id": r.get("test_id", "BANDIT-ISSUE"),
                        "filename": fn,
                        "line_number": r.get("line_number", 1),
                        "issue_text": r.get("issue_text", "Potential security vulnerability"),
                        "issue_severity": r.get("issue_severity", "HIGH").upper(),
                        "code": r.get("code", "")
                    })
    except Exception as e:
        print(f"Error running bandit: {e}")
    finally:
        if os.path.exists(output_file):
            try:
                os.remove(output_file)
            except Exception:
                pass
    return results

def run_semgrep(target_dir: str) -> list:
    """Runs Semgrep if available without cluttering the repo."""
    fd, output_file = tempfile.mkstemp(suffix=".json", prefix="semgrep_")
    os.close(fd)
    results = []
    try:
        result = subprocess.run(
            ["semgrep", "--config=p/ci", target_dir, "--json", "-o", output_file],
            capture_output=True,
            text=True,
            check=False
        )
        if os.path.exists(output_file):
            with open(output_file, "r") as f:
                data = json.load(f)
                semgrep_results = data.get("results", [])
                norm_target = os.path.abspath(target_dir)
                for r in semgrep_results:
                    fn = r.get("path", "")
                    if fn and os.path.isabs(fn):
                        try:
                            fn = os.path.relpath(fn, norm_target)
                        except ValueError:
                            pass
                    extra = r.get("extra", {})
                    results.append({
                        "test_id": r.get("check_id", "SEMGREP-ISSUE").split(".")[-1],
                        "filename": fn,
                        "line_number": r.get("start", {}).get("line", 1),
                        "issue_text": extra.get("message", "Potential security vulnerability"),
                        "issue_severity": extra.get("severity", "ERROR").upper(),
                        "code": extra.get("lines", "")
                    })
    except Exception as e:
        print(f"Semgrep not available or skipped: {e}")
    finally:
        if os.path.exists(output_file):
            try:
                os.remove(output_file)
            except Exception:
                pass
    return results

def run_all_scanners(target_dir: str) -> list:
    """Runs all available security scanners (Bandit, Semgrep) and merges findings."""
    findings = []
    findings.extend(run_bandit(target_dir))
    findings.extend(run_semgrep(target_dir))
    return findings