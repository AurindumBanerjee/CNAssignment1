import math

class Config:
    def __init__(self, filepath="config.txt"):
        self.filepath = filepath
        self.seeds = []          # [(ip, port)]
        self.peer_port = None
        self._parse_config()

    def _parse_config(self):
        with open(self.filepath, "r") as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]

        seed_section = False

        for line in lines:
            if line.upper() == "SEEDS":
                seed_section = True
                continue

            if seed_section and ":" in line:
                ip, port = line.split(":")
                self.seeds.append((ip.strip(), int(port.strip())))

            elif line.startswith("PEER_PORT"):
                _, port = line.split("=")
                self.peer_port = int(port.strip())

    def get_seeds(self):
        return self.seeds

    def get_peer_port(self):
        return self.peer_port

    def get_majority(self):
        """
        Returns ⌊n/2⌋ + 1 for seed consensus
        """
        n = len(self.seeds)
        return math.floor(n / 2) + 1

    def __str__(self):
        return f"Seeds: {self.seeds}, Peer Port: {self.peer_port}"