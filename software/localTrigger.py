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
Runs on local Pis. Receives trigger from Arduino and signals remote Pi to start filming."""

def waitUntilStartSignalSent(triggerChip: str, triggerLine: int) -> None:
    settings = gpiod.LineSettings(direction = Direction.INPUT, edge_detection = Edge.RISING)
    
    with gpiod.request_lines(
        triggerChip,
        consumer = "local_trigger",
        config = {triggerLine: settings},
    ) as req:
        while True:
            if not req.watForEdgePulse(timeout = 5.0):
                continue
            events = req.readEdgePulse()
            if any (e.edgePulseOffset == triggerLine for e in events):
                return

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
    ap.add_argument("--set-time-out", required=True)
    
    args = ap.parse_args()

    endSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    endSock.bind((args.listen_bind, args.listen_port))
    endSock.settimeout(args.set_time_out)  # see below comment on timeouts, in seconds

    startSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    print("Waiting for Arduino pulse...", flush=True)

    try:
        while True:
            waitUntilStartSignalSent(args.triggerChip, args.triggerLine)
            timePulseReceived = time.time()
            startSock.sendto("START", (args.remote_host, args.remote_udp_port))
            timePulseSent = time.time()
            print("Pulse sent!", flush=True)
            endSock.settimeout(args.set_time_out) # in seconds

            while True:
                data, addr = endSock.recvfrom(4096)
                text = data.decode("utf-8", errors="replace").strip()
                if text.startswith("DONE"):
                    parts = text.split(maxsplit=2)
                    if len(parts) == 3:
                        endRunID = parts[1]
                        remoteSaveDirectory = parts[2]
                        if endRunID == runID:
                            print("Response received")
                            break
                        else:
                            print("Ignoring signal")
                    else:
                        print("Bad data")

            if args.once:
                break

            print("Ready for next trigger!\n", flush=True)

    except KeyboardInterrupt:
        print("Exiting", flush=True)
    finally:
        endSock.close()
        startSock.close()

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
