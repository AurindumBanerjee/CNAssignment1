import subprocess
import sys
import time
import socket
import threading
import atexit

BASE_SEED_PORT = 5000
BASE_PEER_PORT = 6000


def port_free(port, host="127.0.0.1", timeout=1.0):
    """Return True if nothing is listening on (host, port)."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return False
    except OSError:
        return True


def wait_for_port(port, host="127.0.0.1", attempts=20, delay=0.5):
    """Block until a process is listening or until we give up."""
    for _ in range(attempts):
        if not port_free(port, host):
            return True
        time.sleep(delay)
    return False


def kill_child_processes():
    for p in processes:
        try:
            p.terminate()
        except Exception:
            pass


def start_process(cmd):
    p = subprocess.Popen(cmd)
    processes.append(p)
    return p


def spawn_group(base_port, count, program_name):
    threads = []

    def worker(port):
        if not port_free(port):
            print(f"port {port} already in use, please free it or kill the process")
            return
        start_process([sys.executable, program_name, str(port)])
        if not wait_for_port(port):
            print(f"warning: {program_name} did not open port {port} in time")

    for i in range(count):
        port = base_port + i
        t = threading.Thread(target=worker, args=(port,))
        t.daemon = True
        t.start()
        threads.append(t)

    for t in threads:
        t.join()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python launcher.py <num_seeds> <num_peers>")
        sys.exit(1)

    num_seeds = int(sys.argv[1])
    num_peers = int(sys.argv[2])
    processes = []

    atexit.register(kill_child_processes)

    print(f"starting {num_seeds} seeds...")
    spawn_group(BASE_SEED_PORT, num_seeds, "seed.py")

    print(f"starting {num_peers} peers (will wait for seeds first)...")
    spawn_group(BASE_PEER_PORT, num_peers, "peer.py")

    print(f"launched {num_seeds} seeds and {num_peers} peers")
    print("press Ctrl-C to terminate all processes")

    try:
        # keep the launcher alive so the atexit handler can run
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("shutting down")
        kill_child_processes()
