from __future__ import annotations
import argparse
import csv
import os
import socket
import time
from datetime import datetime
import cv2
from ultralytics import YOLO
from picamera2 import Picamera2
from libcamera import Transform

'''Run this on remote Pi. localTrigger.py tells remoteDaemon.py to start recording. Footage is saved locally on the remote Pi.'''


def recordHelper(
    *,
    picam2: Picamera2,
    model: YOLO,
    outputDir: str,
    frameRate: float,
    capDur: float,
    conf: float,
) -> tuple[str, str]:
    os.makedirs(outputDir, exist_ok=True)

    frame = picam2.capture_array()
    if frame.shape[2] == 4:
        frame = frame[:, :, :3]
    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    h, w = frame.shape[:2]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    vidPath = os.path.join(outputDir, f"capture_{timestamp}.avi")
    csvPath = os.path.join(outputDir, f"detections_{timestamp}.csv")

    out = cv2.VideoWriter(
        vidPath,
        cv2.VideoWriter_fourcc(*"XVID"),
        frameRate,
        (w, h),
    )

    interval = 1.0 / frameRate
    maxFrames = int(capDur * frameRate)

    with open(csvPath, "w", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["timestamp", "x1", "y1", "x2", "y2", "cx", "cy", "conf", "class"])

        prevTime = time.time()
        i = 0

        while i < maxFrames:
            now = time.time()
            if now - prevTime < interval:
                continue
            prevTime = now

            frame = picam2.capture_array()
            if frame.shape[2] == 4:
                frame = frame[:, :, :3]
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            results = model(frame, verbose=False, conf=conf)
            ts = time.time()

            if len(results[0].boxes) > 0:
                confidences = [float(box.conf[0]) for box in results[0].boxes]
                topIndex = confidences.index(max(confidences))
                topBox = results[0].boxes[topIndex] # Only places 1 bounding box, need to remove if you're trackinfg multiple urchins.

                x1, y1, x2, y2 = map(int, topBox.xyxy[0].tolist())
                conf = float(topBox.conf[0])
                cls = int(topBox.cls[0])

                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2
                writer.writerow([ts, x1, y1, x2, y2, cx, cy, conf, cls])

                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 200, 0), 2)
                label = f"{model.names[cls]} {conf:.2f}"
                cv2.putText(
                   frame, label, (x1, y1 - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 200, 0), 1, cv2.LINE_AA
                )

            out.write(frame)
            i += 1

    out.release()
    return vidPath, csvPath

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--listen-port", type=int, default=5005)
    ap.add_argument("--local-ip", required=True)
    ap.add_argument("--local-port", type=int, default=5006)
    ap.add_argument("--model-path")
    ap.add_argument("--frame-rate", type=float, default=1.0)
    ap.add_argument("--capture-duration", type=float, default=120.0) # in seconds
    ap.add_argument("--width", type=int, default=4608)
    ap.add_argument("--height", type=int, default=2592)
    ap.add_argument("--conf-threshold", type=float, default=0.5)
    ap.add_argument("--output-folder")  
    args = ap.parse_args()

    model = YOLO(args.model_path)

    picam2 = Picamera2()
    picam2.configure(picam2.create_video_configuration(main={"size": (args.width, args.height)}))
    picam2.start()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.bind, args.listen_port))
    sock.settimeout(None)

    done_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    os.makedirs(args.output_folder, exist_ok=True)

    print("Expected message: START", flush=True)

    try:
        while True:
            data, addr = sock.recvfrom(2048)
            msg = data.decode("utf-8", errors="replace").strip()
            if not msg:
                continue

            if msg.startswith("START"):
                print("Starting recording!")
                parts = msg.split(maxsplit=1)
                run_id = parts[1] if len(parts) == 2 else datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                run_dir = os.path.join(args.output_folder, f"run_{run_id}")

                t0 = time.time()
                vidPath, csvPath = recordHelper(
                    picam2=picam2,
                    model=model,
                    outputDir=run_dir,
                    frameRate=args.frameRate,
                    capDur=args.capture_duration,
                    conf=args.conf,
                )
                t1 = time.time()

                done_msg = f"DONE {run_id} {run_dir}"
                print("Finished recording! Press Ctrl + C to stop the program")
                done_sock.sendto(done_msg.encode("utf-8"), (args.local_ip, args.local_port))
                
            else:
                print("Failed run :(")

    except KeyboardInterrupt:
        print("Exiting", flush=True)
    finally:
        try:
            picam2.stop()
        except Exception:
            pass
        sock.close()
        done_sock.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
