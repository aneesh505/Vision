from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
from backend.pipeline import run_self_healing_pipeline

app = FastAPI(title="AegisAI Self-Healing DevSecOps API", version="1.0.0")

# Serve frontend static files
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend"))
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="frontend-static")

@app.get("/")
def serve_index():
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "AegisAI API is running. Frontend index.html not found."}

class ScanRequest(BaseModel):
    repo_url: str
    branch: str = "main"
    enable_bandit: bool = True
    enable_semgrep: bool = True
    enable_docker: bool = True
    enable_pr: bool = True

# In-memory job storage for demo
jobs_db = {}

@app.post("/api/scan")
def start_scan(req: ScanRequest, background_tasks: BackgroundTasks):
    job_id = os.urandom(4).hex()
    jobs_db[job_id] = {"status": "running", "repo_url": req.repo_url}

    def background_job():
        try:
            res = run_self_healing_pipeline(
                req.repo_url,
                req.branch,
                enable_bandit=req.enable_bandit,
                enable_semgrep=req.enable_semgrep,
                enable_docker=req.enable_docker,
                enable_pr=req.enable_pr
            )
            jobs_db[job_id] = {"status": "completed", "result": res}
        except Exception as e:
            jobs_db[job_id] = {"status": "failed", "error": str(e)}

    background_tasks.add_task(background_job)
    return {"job_id": job_id, "status": "started"}

@app.get("/api/runs/{job_id}")
def get_run_status(job_id: str):
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs_db[job_id]

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        reload_excludes=["sandbox_workspaces/*", "output/*", "tmp/*"],
    )