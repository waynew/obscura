#!/usr/bin/env python3

import os
import pathlib
import time

from datetime import datetime

IMG_EXTENSIONS = [
    '.jpg',
    '.jpeg',
    '.cr2',
    '.png',
]

SRC_FOLDER = pathlib.Path(r'e:\pictures').resolve()
DST_FOLDER = pathlib.Path(r'e:\organized').resolve()

paths_to_walk = [SRC_FOLDER]
to_copy = set()

start = time.time()
while paths_to_walk:
    next_path = paths_to_walk.pop()
    print(next_path)
    try:
        for thing in next_path.iterdir():
            if thing.is_dir():
                paths_to_walk.append(thing)
            elif thing.suffix.lower() in IMG_EXTENSIONS:
                to_copy.add(thing)
    except PermissionError as e:
        print('Warning:', e)
end = time.time()

lapsed = end-start
seconds = lapsed % 60
left = (lapsed - seconds)/60
minutes = int(left % 60)
left = (left - minutes)/60
hours = int(left % 24)

time_spent = ''
if hours:
    time_spent += f'{hours}h'
time_spent += f'{minutes}m'
time_spent += f'{seconds:.2f}s'

print(time_spent)
print(len(to_copy))
f = list(to_copy)[0]
print(f)
print(f.stat())
print(datetime.fromtimestamp(f.stat().st_ctime))
print(datetime.fromtimestamp(f.stat().st_mtime))
