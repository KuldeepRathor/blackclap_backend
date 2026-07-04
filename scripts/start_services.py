#!/usr/bin/env python3
import os
import subprocess
import sys
import time

from dotenv import load_dotenv


def load_ssot_environment() -> str:
    """Resolve and load the external environment file based on the ENV variable."""
    env_name = os.getenv("ENV", "development")
    print(f"[*] Starting services in environment: {env_name}")

    # Compute paths relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))  # scripts/
    project_root = os.path.dirname(script_dir)  # blackclap_backend/
    parent_dir = os.path.dirname(project_root)  # blackclap/

    # Target external SSOT file:
    # /Users/kuldeeprathor/codes/backend/blackclap/ssot.{ENV}.env
    ssot_env_file = os.path.join(parent_dir, f"ssot.{env_name}.env")

    # Fallback paths
    project_ssot_env = os.path.join(project_root, f"ssot.{env_name}.env")
    local_env = os.path.join(project_root, ".env")

    env_file_to_load = None

    if os.path.exists(ssot_env_file):
        env_file_to_load = ssot_env_file
    elif os.path.exists(project_ssot_env):
        env_file_to_load = project_ssot_env
    elif os.path.exists(local_env):
        env_file_to_load = local_env
        print(
            f"[*] Warning: SSOT file not found. "
            f"Falling back to local .env at: {local_env}"
        )
    else:
        print("[!] Warning: No environment variable file (.env or ssot.*.env) found!")

    if env_file_to_load:
        print(f"[*] Loading environment variables from: {env_file_to_load}")
        # load_dotenv with override=True to prioritize
        # environment variables defined in the file
        load_dotenv(env_file_to_load, override=True)
    else:
        print("[*] Proceeding with system environment variables.")

    return project_root


def main():
    project_root = load_ssot_environment()

    # Retrieve port from env or default to 8000
    port = int(os.getenv("PORT", "8000"))

    # Resolve correct Python interpreter from virtual environment if present
    python_exe = sys.executable
    venv_python = os.path.join(project_root, "venv", "bin", "python")
    dot_venv_python = os.path.join(project_root, ".venv", "bin", "python")

    if os.path.exists(venv_python):
        python_exe = venv_python
    elif os.path.exists(dot_venv_python):
        python_exe = dot_venv_python

    print(f"[*] Using Python interpreter: {python_exe}")

    # Construct environment copy and ensure virtualenv binaries are in PATH
    sub_env = os.environ.copy()
    venv_bin = os.path.join(project_root, "venv", "bin")
    dot_venv_bin = os.path.join(project_root, ".venv", "bin")
    path_dirs = sub_env.get("PATH", "").split(os.pathsep)
    if os.path.exists(venv_bin) and venv_bin not in path_dirs:
        path_dirs.insert(0, venv_bin)
    if os.path.exists(dot_venv_bin) and dot_venv_bin not in path_dirs:
        path_dirs.insert(0, dot_venv_bin)
    sub_env["PATH"] = os.pathsep.join(path_dirs)

    processes = []

    # 1. Start FastAPI app (uvicorn app.main:app)
    api_command = (
        f"{python_exe} -m uvicorn app.main:app --host 0.0.0.0 --port {port} --reload"
    )
    print(f"[*] Starting FastAPI API Service on port {port}...")
    try:
        api_proc = subprocess.Popen(
            api_command, shell=True, cwd=project_root, env=sub_env
        )
        processes.append(api_proc)
    except Exception as e:
        print(f"[!] Error starting FastAPI service: {e}")
        sys.exit(1)

    # Brief delay to prevent race conditions on port binding or initialization
    time.sleep(2)

    # 2. Start Celery worker (celery -A app.workers.celery_app worker --loglevel=info)
    celery_command = (
        f"{python_exe} -m celery -A app.workers.celery_app worker --loglevel=info"
    )
    print("[*] Starting Celery worker...")
    try:
        celery_proc = subprocess.Popen(
            celery_command, shell=True, cwd=project_root, env=sub_env
        )
        processes.append(celery_proc)
    except Exception as e:
        print(f"[!] Error starting Celery worker: {e}")
        # Terminate any running process
        for p in processes:
            p.terminate()
        sys.exit(1)

    print("\n[+] All services started successfully. Press Ctrl+C to stop.")

    try:
        # Keep the parent process running and monitor sub-processes
        while True:
            for p in processes:
                # Check if a process has finished/crashed
                status = p.poll()
                if status is not None:
                    print(
                        f"\n[!] Process with PID {p.pid} "
                        f"exited with status code {status}"
                    )
                    raise KeyboardInterrupt
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Stopping all services...")
        for p in processes:
            if p.poll() is None:
                print(f"[*] Terminating process with PID {p.pid}...")
                p.terminate()

        # Wait for all processes to close
        for p in processes:
            p.wait()
        print("[+] All services stopped cleanly.")


if __name__ == "__main__":
    main()
