from __future__ import annotations
import argparse
import os
import shlex
import socket
import subprocess
import time
from datetime import datetime
import gpiod
from gpiod.line import Direction, Edge

"""
Runs on local Pis. Does the following:
1) Waits for pulse from pictus 2 Arduino.

2) Sends firing key to remote Pis to begin recording.

3) Receives video files from remote Pis once recording
is complete. Again, note that this sometimes fails if your 
recording contains many frames or if your network is unable
to support large data transfers. If this step times out, your 
output files will be saved automatically onto the remote Pi.
"""

def run(cmd: list[str], *, check: bool = True) -> None:
    print("\n$", " ".join(shlex.quote(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=check)


def wait_for_trigger(trigger_chip: str, trigger_line: int) -> None:
    settings = gpiod.LineSettings(direction = Direction.INPUT, edge_detection = Edge.RISING)
    
    with gpiod.request_lines(
        trigger_chip,
        consumer = "local_trigger",
        config = {trigger_line: settings},
    ) as req:
        while True:
            if not req.wait_edge_events(timeout = 5.0):
                continue
            events = req.read_edge_events()
            if any (e.line_offset == trigger_line for e in events):
                return

def rsync_from(remote_user: str, remote_host: str, remote_dir: str, local_out: str) -> None:
    os.makedirs(local_out, exist_ok=True)
    remote = f"{remote_user}@{remote_host}:{remote_dir}/"
    run(["rsync", "-av", "--partial", remote, f"{local_out}/"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trigger-chip", default="/dev/gpiochip0")
    ap.add_argument("--trigger-line", type=int, default=17)
    ap.add_argument("--remote-host", required=True)
    ap.add_argument("--remote-user")
    ap.add_argument("--remote-udp-port", type=int, default=5005)
    ap.add_argument("--listen-bind", default="0.0.0.0")
    ap.add_argument("--listen-port", type=int, default=5006)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--local-out", required=True)
    ap.add_argument("--set-time-out", required=True)
    
    args = ap.parse_args()

    local_out = os.path.abspath(os.path.expanduser(args.local_out))
    os.makedirs(local_out, exist_ok=True)

    done_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    done_sock.bind((args.listen_bind, args.listen_port))
    done_sock.settimeout(args.set_time_out)  # see below comment on timeouts, in seconds

    start_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    print("Waiting for Arduino pulse...", flush=True)

    try:
        while True:
            wait_for_trigger(args.trigger_chip, args.trigger_line)
            t_pulse = time.time()

            run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            msg = f"START {run_id}".encode("utf-8")

            start_sock.sendto(msg, (args.remote_host, args.remote_udp_port))
            t_sent = time.time()

            print(f"Pulse at {t_pulse:.6f}. Sent firing key at {t_sent:.6f} (delta {(t_sent - t_pulse)*1000:.1f} ms)", flush=True)

            # Below line needs to be modified based on length of recording.
            # The timeout must be longer than the length of the recording.
            # If you want to collect multiple consecutive videos, the timeout
            # should be longer than all videos (e.g. three consecutive 60 s
            # videos require a timeout of at least 180 s).
            # You will need to rerun localTrigger.py once timeout occurs.
            done_sock.settimeout(args.set_time_out) # in seconds

            while True:
                data, addr = done_sock.recvfrom(4096)
                text = data.decode("utf-8", errors="replace").strip()
                if text.startswith("DONE"):
                    parts = text.split(maxsplit=2)
                    if len(parts) == 3:
                        done_run_id = parts[1]
                        remote_dir = parts[2]
                        if done_run_id == run_id:
                            print(f"Proper response received from {addr}: {text}", flush=True)
                            rsync_from(args.remote_user, args.remote_host, remote_dir, local_out)
                            break
                        else:
                            print(f"Ignoring, response was from different run_id={done_run_id}", flush=True)
                    else:
                        print(f"Error, data is corrupt: {text!r}", flush=True)

            if args.once:
                break

            print("Ready for next trigger.\n", flush=True)

    except KeyboardInterrupt:
        print("Exiting.", flush=True)
    finally:
        done_sock.close()
        start_sock.close()

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
