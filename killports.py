import subprocess
import re


def get_pids_on_port(port):
    """
    Returns a set of PIDs using the given port.
    """
    result = subprocess.run(
        ["netstat", "-ano"],
        capture_output=True,
        text=True
    )

    lines = result.stdout.splitlines()
    pids = set()

    for line in lines:
        if f":{port} " in line:
            parts = re.split(r"\s+", line.strip())
            if len(parts) >= 5:
                pid = parts[-1]
                if pid.isdigit():
                    pids.add(pid)

    return pids


def kill_pid(pid):
    """
    Force kills a PID.
    """
    try:
        subprocess.run(["taskkill", "/PID", pid, "/F"], check=True)
        print(f"✔ Killed PID {pid}")
    except subprocess.CalledProcessError:
        print(f"✖ Failed to kill PID {pid}")


def kill_port_range(start_port, count):
    """
    Kill processes running from start_port to start_port + count - 1
    """
    end_port = start_port + count - 1

    for port in range(start_port, end_port + 1):
        pids = get_pids_on_port(port)

        if pids:
            print(f"\nPort {port} is in use by PIDs: {', '.join(pids)}")
            for pid in pids:
                kill_pid(pid)
        else:
            print(f"Port {port} is free.")


if __name__ == "__main__":
    try:
        x = int(input("Enter number of 5000-series ports: "))
        y = int(input("Enter number of 6000-series ports: "))

        print("\nChecking 5000-series ports...")
        kill_port_range(5000, x)

        print("\nChecking 6000-series ports...")
        kill_port_range(6000, y)

        print("\nDone.")

    except ValueError:
        print("Please enter valid integers.")