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


if __name__ == "__main__":
    try:
        port = int(input("Enter the port number to kill: "))

        pids = get_pids_on_port(port)

        if not pids:
            print(f"Port {port} is already free.")
        else:
            print(f"Port {port} is being used by PIDs: {', '.join(pids)}")
            for pid in pids:
                kill_pid(pid)

        print("Done.")

    except ValueError:
        print("Please enter a valid port number.")