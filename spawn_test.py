import subprocess, time

# start three seeds
seeds = []
for port in (5000,5001,5002):
    p = subprocess.Popen(["python","seed.py",str(port)])
    seeds.append(p)
    time.sleep(0.1)

# start multiple peers quickly
tails=[]
for port in range(6000,6006):
    p = subprocess.Popen(["python","peer.py",str(port)])
    tails.append(p)
    time.sleep(0.05)

print("launched")

# run for a while then kill a peer to test removal
time.sleep(5)
print("killing peer 6002")
for p in tails:
    if p.args[-1]=="6002":
        p.kill()
        break

# let system continue
try:
    time.sleep(10)
except KeyboardInterrupt:
    pass

# cleanup
for p in seeds+tails:
    try:p.terminate()
    except: pass
