# AutoSec Agent (AegisAI)
One-line pitch: An autonomous DevSecOps agent that discovers security vulnerabilities in any GitHub repository, fixes them in an ephemeral Docker sandbox, proves each fix with regression tests, and opens a precise Pull Request for human review.

![AegisAI Dashboard](https://img.shields.io/badge/Status-Production%20Ready-cyan?style=for-the-badge&logo=security)

## 1. Problem
Traditional security scans (SAST) happen late in the development lifecycle, generating noisy alerts that require tedious manual verification to determine exploitability. Furthermore, patching vulnerabilities manually is time-consuming and risks introducing regressions that break existing application features.

## 2. How it works
The autonomous pipeline executes the following stages sequentially:
Clone → Dependency Install → Scan (Bandit & Semgrep) → Baseline Tests → AI Fix Generation → Regression Test Verification (Must Pass) → Fork, Commit & Pull Request → Human Review

> **Rule:** The LLM writes the patch, the test suite decides its validity, and the human approves the Pull Request.

## 3. Features
- **Multi-Engine Scanning**: Combines Bandit (Python AST) and Semgrep (Multi-language taint analysis).
- **Ephemeral Docker Sandboxing**: Runs tests and patches inside isolated `python:3.11-slim` containers with network limits and automatic container removal (`remove=True`).
- **Self-Healing Retry Loop**: Automatically catches syntax errors or test regressions, re-prompting the LLM up to 3 times to self-correct.
- **Granular Git Commits & PRs**: Commits each fix separately with exact error descriptions as commit messages and formats a clean PR body.
- **Real-Time Live Dashboard**: Responsive dark/light UI streaming live agent activity logs and sandbox terminal output.

## 4. Supported vulnerabilities (current scope)
| Vulnerability Type | CWE / Rule ID | Remediation Strategy |
| :--- | :--- | :--- |
| **SQL Injection** | CWE-89 (B608) | Replace raw string formatting / concatenation with parameterized queries (`?`). |
| **Reflected XSS** | CWE-79 | HTML-escape user input using `markupsafe.escape`. |
| **Hardcoded Secrets** | CWE-259 (B105) | Move secrets to environment variables (`os.environ.get`) with secure fallbacks. |
| **Command Injection** | CWE-78 (B602) | Remove `shell=True` and pass command arguments as a safe list to `subprocess`. |
| **Debug Mode Enabled** | CWE-94 (B201) | Read debug mode from environment variables (`FLASK_DEBUG`) instead of hardcoding `debug=True`. |

*Scope*: Python/Flask repositories with standard dependency files (`requirements.txt`, `setup.py`, `pyproject.toml`).

## 5. Tech stack
| Component | Technology |
| :--- | :--- |
| **Language** | Python 3.11+ |
| **API Framework** | FastAPI & Uvicorn |
| **Security Scanners** | Bandit, Semgrep |
| **Test Runner** | pytest |
| **Sandbox Environment** | Docker SDK & Ephemeral Containers |
| **GitHub Integration** | PyGithub & Git CLI |
| **LLM Provider** | OpenAI / Anthropic / OmniRoute |
| **Frontend** | HTML5, Tailwind CSS, Lucide Icons, Vanilla JS |

## 6. Project structure
```text
Vision/
├── backend/
│   ├── main.py             # FastAPI server and job runner API endpoints
│   ├── pipeline.py         # Core self-healing agentic workflow orchestrator
│   ├── steps/
│   │   ├── scan.py         # Bandit & Semgrep security scanner wrappers
│   │   ├── fix.py          # LLM security patch generation client
│   │   └── pr.py           # GitHub fork, commit, push & PR automation
│   ├── sandbox/
│   │   └── docker_runner.py# Ephemeral Docker container sandbox manager
│   └── llm/
│       ├── client.py       # LLM API client wrapper
│       └── prompts.py      # Security engineering & remediation prompt templates
├── frontend/
│   ├── index.html          # Dashboard UI with stage stepper and live terminal
│   ├── style.css           # High-tech cyber theme (Light/Dark mode & glassmorphism)
│   └── app.js              # Frontend controller & real-time job polling
├── requirements.txt        # Python backend dependencies
├── LICENSE                 # MIT License
└── .env                    # Local environment config (gitignored; not committed)
```

## 7. Getting Started & Deployment

You can use AegisAI either via the hosted live web service or by running it locally on your machine.

### Option A: Use the Hosted Web App (Recommended)
You can access and use AegisAI directly without installing anything:
- **Live URL**: [https://aegisai-devsecops.onrender.com](https://aegisai-devsecops.onrender.com) *(Replace with your live Render URL)*
1. Open the web app link in your browser.
2. Enter your GitHub repository URL and click **Trigger Agent Loop**.

---

### Option B: Local Development Setup
If you want to run your own instance of AegisAI locally:

#### Prerequisites
- Python 3.11+
- Docker Desktop (optional; falls back to local subprocess if unavailable)
- GitHub Personal Access Token (classic with `repo` scope)
- LLM API Key (OpenAI / Anthropic / OmniRoute)

#### Installation
```bash
git clone https://github.com/aneesh505/Vision.git
cd Vision
pip install -r requirements.txt
```

#### Configuration
Create a `.env` file in the root directory:
```env
GITHUB_TOKEN=ghp_your_github_personal_access_token
LLM_API_KEY=your_llm_api_key
LLM_PROVIDER=your_llm_provider
LLM_BASE_URL=base_url
LLM_MODEL=llm_model
```

#### Run Locally
Start the FastAPI backend server:
```bash
python -m backend.main
```
Then open your browser at **`http://localhost:8000`**.

## 8. Usage
1. Paste any public or authorized private GitHub repository URL into the input field.
2. Select desired engine toggles (Bandit, Semgrep, Docker Sandbox, PR Auto-Generation).
3. Click **Trigger Agent Loop** and watch the live stage progress and sandbox terminal.
4. Once verified, click the generated Pull Request link to review and merge the changes on GitHub.

## 9. Demo target
- **Demo Repository**: `https://github.com/aneesh505/test` (or `aneesh505/demo2`)
- **Planted Bugs**: SQL Injection, Hardcoded Secrets, Command Injection, Reflected XSS, and Debug Mode Enabled.
- ⚠️ *Warning: Intentionally vulnerable test applications. Do not deploy in production.*

## 10. Safety and limitations
- Untrusted code is meant to run inside ephemeral, isolated Docker containers with network and memory limits. If Docker is unavailable, the pipeline falls back to a local subprocess.
- The agent never merges code automatically; human approval is strictly required via Pull Request review.
- Generated patches are verified against automated test suites but remain subject to human review.
- Exploit verification covers supported vulnerability classes within configured test scopes.

## 11. Roadmap
- Expand multi-language support (JavaScript/TypeScript, Go, Java).
- Support repositories without pre-existing dependency files via automatic dependency inference.
- Real-time runtime application protection (RASP) integration.

## 12. Team and license
- **Team**: NMAMIT Students
- **Event**: Hackloop S05
- **License**: MIT License
