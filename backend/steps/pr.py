import os
import subprocess
import uuid
from github import Github
from dotenv import load_dotenv

load_dotenv()

def create_pull_request(repo_url: str, branch_name: str, title: str, body: str, workspace_dir: str = None, fixes_applied: list = None) -> str:
    """
    Automates the Fork, Commit, Push, and PR workflow without temp files or co-author attribution.
    """
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("GitHub token not configured. Skipping PR creation.")
        return ""

    g = Github(token)
    try:
        user = g.get_user()
        username = user.login
    except Exception as e:
        print(f"GitHub authentication failed (check GITHUB_TOKEN): {e}")
        return ""

    # Extract owner/repo from repo_url
    clean_url = repo_url.strip().removesuffix("/").removesuffix(".git").rstrip("/")
    for prefix in ("https://github.com/", "http://github.com/", "git@github.com:"):
        if clean_url.startswith(prefix):
            clean_url = clean_url[len(prefix):]
            break

    parts = clean_url.split("/")
    if len(parts) < 2:
        raise ValueError(f"Invalid repository URL: {repo_url}")

    owner, repo_name = parts[0], parts[1]
    upstream_full_name = f"{owner}/{repo_name}"

    try:
        upstream_repo = g.get_repo(upstream_full_name)
    except Exception as e:
        print(f"Error accessing upstream repository {upstream_full_name}: {e}")
        return ""

    # 1. Automatically fork repository to authenticated user's account
    try:
        print(f"Forking {upstream_full_name} to user account ({username})...")
        my_fork = user.create_fork(upstream_repo)
    except Exception as e:
        print(f"Fork may already exist or encountered note: {e}")
        my_fork = g.get_repo(f"{username}/{repo_name}")

    # Build PR body lines as requested:
    # AegisAI Autonomous Security Remediation
    # - [B105] app.py:8 — "Possible hardcoded password: 'super-secret-key-123'"
    pr_body_lines = ["AegisAI Autonomous Security Remediation"]
    if fixes_applied:
        for f_app in fixes_applied:
            if f_app.get("applied"):
                finding = f_app.get("finding", {})
                test_id = finding.get("test_id", "SECURITY")
                filename = finding.get("filename", "app.py")
                line_no = finding.get("line_number", 1)
                issue_text = finding.get("issue_text", "Vulnerability detected")
                pr_body_lines.append(f'- [{test_id}] {filename}:{line_no} — "{issue_text}"')

    pr_body = "\n".join(pr_body_lines)
    pr_title = "🔐 AegisAI: Automated Security Remediation & Vulnerability Fix"

    # 2. Commit and push changes if workspace_dir is provided
    pr_branch = f"aegis-security-fix-{uuid.uuid4().hex[:6]}"
    if workspace_dir and os.path.exists(workspace_dir):
        try:
            print(f"Committing patches in workspace {workspace_dir}...")
            subprocess.run(["git", "config", "user.name", "AegisAI Security Bot"], cwd=workspace_dir, check=False)
            subprocess.run(["git", "config", "user.email", "bot@aegisai.local"], cwd=workspace_dir, check=False)
            subprocess.run(["git", "checkout", "-b", pr_branch], cwd=workspace_dir, check=True)

            # Create granular commits for each applied fix without co-author or temp files
            if fixes_applied:
                for f_app in fixes_applied:
                    if f_app.get("applied"):
                        finding = f_app.get("finding", {})
                        filename = finding.get("filename", "app.py")
                        issue_text = finding.get("issue_text", "Vulnerability detected")

                        commit_msg = f"{issue_text}"

                        subprocess.run(["git", "add", filename], cwd=workspace_dir, check=False)
                        diff_check = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=workspace_dir, check=False)
                        if diff_check.returncode != 0:
                            subprocess.run(["git", "commit", "-F", "-"], input=commit_msg.encode("utf-8"), cwd=workspace_dir, check=True)

            # Catch-all for any remaining modified files
            subprocess.run(["git", "add", "."], cwd=workspace_dir, check=False)
            diff_check = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=workspace_dir, check=False)
            if diff_check.returncode != 0:
                fallback_msg = "Security remediation and hardening"
                subprocess.run(["git", "commit", "-F", "-"], input=fallback_msg.encode("utf-8"), cwd=workspace_dir, check=True)

            fork_clone_url = f"https://{token}@github.com/{username}/{repo_name}.git"
            subprocess.run(["git", "remote", "set-url", "origin", fork_clone_url], cwd=workspace_dir, check=False)

            print(f"Pushing branch {pr_branch} to fork {username}/{repo_name}...")
            push_res = subprocess.run(["git", "push", "-u", "origin", pr_branch], cwd=workspace_dir, capture_output=True, text=True, check=False)
            if push_res.returncode != 0:
                print(f"Git push failed: {push_res.stderr}")
                return ""
        except Exception as git_err:
            print(f"Git commit/push error: {git_err}")
            return ""

    # 3. Create Pull Request from user's fork branch to upstream repo
    try:
        print(f"Creating Pull Request on {upstream_full_name} from {username}:{pr_branch}...")
        pr = upstream_repo.create_pull(
            title=pr_title,
            body=pr_body,
            head=f"{username}:{pr_branch}",
            base=upstream_repo.default_branch
        )
        print(f"Pull Request successfully created: {pr.html_url}")
        return pr.html_url
    except Exception as e:
        print(f"Error creating pull request: {e}")
        return ""

if __name__ == "__main__":
    print("pr.py module loaded successfully.")