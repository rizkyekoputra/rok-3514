#!/usr/bin/env python3
"""Turn a RoK ranking screen recording into images that are easy to read.

Writes into OUT_DIR:
  start_XX.png   first 1.5 s at 10 fps (rank 1 is only on screen for a moment)
  stack_XX.png   1 fps frames, cropped to the ranking list, 4 frames per image

Usage: .venv/bin/python extract_frames.py VIDEO OUT_DIR [--crop L,T,R,B]
Default crop fits WhatsApp-compressed 848x392 recordings.
"""
import argparse
import glob
import os
import subprocess

from PIL import Image, ImageDraw

p = argparse.ArgumentParser()
p.add_argument('video')
p.add_argument('out')
p.add_argument('--crop', default='145,95,705,385')
p.add_argument('--per-image', type=int, default=4)
a = p.parse_args()
crop = tuple(int(v) for v in a.crop.split(','))
raw = os.path.join(a.out, 'raw')
os.makedirs(raw, exist_ok=True)

subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', a.video, '-t', '1.5', '-vf', 'fps=10',
                os.path.join(a.out, 'start_%02d.png')], check=True)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', a.video, '-vf', 'fps=1',
                os.path.join(raw, '%03d.png')], check=True)

frames = sorted(glob.glob(os.path.join(raw, '*.png')))
w, h = crop[2] - crop[0], crop[3] - crop[1]
for i in range(0, len(frames), a.per_image):
    group = frames[i:i + a.per_image]
    sheet = Image.new('RGB', (w, h * len(group)))
    for j, f in enumerate(group):
        im = Image.open(f).crop(crop)
        ImageDraw.Draw(im).text((5, 5), os.path.basename(f)[:3], fill='yellow')
        sheet.paste(im, (0, h * j))
    sheet.save(os.path.join(a.out, f'stack_{i // a.per_image + 1:02d}.png'))

print(f'{len(frames)} frames -> {len(glob.glob(os.path.join(a.out, "stack_*.png")))} stacked images, '
      f'{len(glob.glob(os.path.join(a.out, "start_*.png")))} start frames in {a.out}')
