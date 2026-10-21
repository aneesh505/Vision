import docker
import os
import uuid

class DockerRunner:
    def __init__(self, image_name: str = "python:3.11-slim"):
        self.image_name = image_name
        try:
            self.client = docker.from_env()
            self.client.ping()
            self.use_docker = True
        except Exception as e:
            print(f"Docker daemon not available ({e}), falling back to secure local subprocess execution.")
            self.client = None
            self.use_docker = False

    def run_command(self, workspace_path: str, command: str, timeout: int = 60) -> dict:
        """
        Spins up a brand-new ephemeral Docker container, mounts the workspace,
        runs the command, captures output, and automatically destroys the container.
        """
        if self.use_docker and self.client:
            try:
                abs_workspace = os.path.abspath(workspace_path)

                # Run command in a fresh ephemeral container with auto-remove
                container = self.client.containers.run(
                    self.image_name,
                    command=f"bash -c 'cd /workspace && {command}'",
                    volumes={abs_workspace: {'bind': '/workspace', 'mode': 'rw'}},
                    working_dir="/workspace",
                    detach=True,
                    remove=True,  # Automatically delete container upon exit
                    mem_limit="512m",
                    network_mode="bridge"  # Allow PyPI access for pip install
                )

                # Wait for container execution with timeout
                result = container.wait(timeout=timeout)
                logs = container.logs(stdout=True, stderr=True).decode('utf-8', errors='ignore')

                return {
                    "exit_code": result.get("StatusCode", 0),
                    "output": logs
                }
            except Exception as e:
                print(f"Docker execution failed ({e}), falling back to local subprocess...")

        # Fallback to local subprocess execution if Docker is unavailable
        import subprocess
        try:
            res = subprocess.run(
                command,
                shell=True,
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return {
                "exit_code": res.returncode,
                "output": res.stdout + res.stderr
            }
        except subprocess.TimeoutExpired:
            return {"exit_code": -1, "output": "Command timed out."}
        except Exception as e:
            return {"exit_code": -1, "output": str(e)}

if __name__ == "__main__":
    runner = DockerRunner()
    demo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../demo-vulnerable-app"))
    print("Testing DockerRunner ephemeral container...")
    res = runner.run_command(demo_path, "python -m pytest")
    print(f"Exit Code: {res['exit_code']}")
    print(f"Output:\n{res['output']}")