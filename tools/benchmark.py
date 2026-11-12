"""Synthetic processing-only throughput. Excludes camera, Qt and projector latency."""
import argparse
import json
import time
import cv2
import numpy as np
from projection_pen.tracking import ColorTracker, TrackingConfig

parser = argparse.ArgumentParser()
parser.add_argument('--width', type=int, default=1280)
parser.add_argument('--height', type=int, default=720)
parser.add_argument('--frames', type=int, default=300)
args = parser.parse_args()
if min(args.width, args.height, args.frames) < 1:
    parser.error('Positive dimensions and frame count required')
tracker, config = ColorTracker(), TrackingConfig()
frame = np.zeros((args.height, args.width, 3), np.uint8)
cv2.circle(frame, (args.width//2, args.height//2), 12, (0, 255, 0), -1)
for i in range(10):
    tracker.process(frame, i/60, config)
times = []
for i in range(args.frames):
    start = time.perf_counter()
    tracker.process(frame, (i+10)/60, config)
    times.append((time.perf_counter()-start)*1000)
print(json.dumps({'width': args.width, 'height': args.height, 'frames': args.frames,
                  'mean_ms': float(np.mean(times)), 'p95_ms': float(np.percentile(times, 95)),
                  'processing_fps': 1000/float(np.mean(times)),
                  'scope': 'synthetic HSV tracking only; not end-to-end hardware performance'}, indent=2))
