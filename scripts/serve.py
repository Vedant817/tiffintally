"""Background daemon lifecycle manager for TiffinTally Uvicorn server.

Avoids 600s task timeouts, socket leaks (Errno 10048), and unmanaged zombie PIDs.
Usage:
    python -m scripts.serve status
    python -m scripts.serve start
    python -m scripts.serve stop
    python -m scripts.serve restart
"""

import argparse
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

HOST = "127.0.0.1"
PORT = 8000
HEALTH_URL = f"http://{HOST}:{PORT}/health"


def find_pid_on_port(port: int = PORT) -> list[int]:
    pids = []
    if sys.platform == "win32":
        try:
            output = subprocess.check_output(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"(Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue).OwningProcess",
                ],
                text=True,
            ).strip()
            for line in output.splitlines():
                line = line.strip()
                if line.isdigit():
                    pid = int(line)
                    if pid > 0 and pid not in pids:
                        pids.append(pid)
        except Exception:
            pass
    return pids


def is_healthy() -> bool:
    try:
        req = urllib.request.Request(HEALTH_URL)
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def stop_server() -> bool:
    pids = find_pid_on_port(PORT)
    if not pids:
        print(f"No process listening on port {PORT}.")
        return True

    print(f"Stopping {len(pids)} process(es) on port {PORT}: {pids}...")
    for pid in pids:
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
            else:
                os.kill(pid, 9)
        except Exception as e:
            print(f"Warning: could not kill PID {pid}: {e}")

    # Wait up to 3s for port to be released
    for _ in range(30):
        time.sleep(0.1)
        if not find_pid_on_port(PORT):
            print("Server stopped and port released.")
            return True

    print("Port not released after stopping.")
    return False


def start_server() -> bool:
    if is_healthy():
        pids = find_pid_on_port(PORT)
        print(f"Server is already running and healthy on http://{HOST}:{PORT} (PID(s): {pids}).")
        return True

    # Clean up any stale/unresponsive processes
    pids = find_pid_on_port(PORT)
    if pids:
        print(f"Cleaning up stale process(es) {pids} on port {PORT}...")
        stop_server()

    print(f"Starting TiffinTally Uvicorn server on http://{HOST}:{PORT}...")
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000008  # DETACHED_PROCESS

    proc = subprocess.Popen(
        ["uv", "run", "uvicorn", "tiffintally.app:app", "--host", HOST, "--port", str(PORT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
        close_fds=True,
    )

    print(f"Spawned server daemon (PID {proc.pid}). Waiting for health check...")
    for i in range(40):
        time.sleep(0.25)
        if is_healthy():
            print(
                f"Server is healthy and ready at http://{HOST}:{PORT}/ (in {(i + 1) * 0.25:.1f}s)"
            )
            return True

    print("Server failed to become healthy within 10 seconds.")
    return False


def server_status():
    pids = find_pid_on_port(PORT)
    healthy = is_healthy()
    if healthy:
        print(f"ACTIVE: Server running on http://{HOST}:{PORT}/ (PID(s): {pids}) - Health: 200 OK")
        return 0
    elif pids:
        print(f"WARNING: Port {PORT} occupied by PID(s) {pids} but /health is not responding.")
        return 1
    else:
        print(f"INACTIVE: No server running on port {PORT}.")
        return 2


def main():
    parser = argparse.ArgumentParser(description="TiffinTally server manager")
    parser.add_argument(
        "action", choices=["start", "stop", "restart", "status"], default="status", nargs="?"
    )
    args = parser.parse_args()

    if args.action == "status":
        sys.exit(server_status())
    elif args.action == "stop":
        sys.exit(0 if stop_server() else 1)
    elif args.action == "start":
        sys.exit(0 if start_server() else 1)
    elif args.action == "restart":
        stop_server()
        time.sleep(0.5)
        sys.exit(0 if start_server() else 1)


if __name__ == "__main__":
    main()
