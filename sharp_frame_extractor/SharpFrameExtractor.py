import math
import multiprocessing
import os
import time
from multiprocessing import Pool
from pathlib import Path

import cv2
import tqdm

from sharp_frame_extractor.SFEWorker import init_worker, extract
from sharp_frame_extractor.estimator.BaseEstimator import BaseEstimator


class SharpFrameExtractor:
    def __init__(self, estimator: BaseEstimator,
                 min_sharpness=-1,
                 crop_factor=0.25,
                 output_format="png",
                 cpu_count=multiprocessing.cpu_count(),
                 force_cpu_count=False,
                 extract_all=False,
                 preview=False):
        self.estimator = estimator
        self.min_sharpness = min_sharpness
        self.crop_factor = crop_factor
        self.output_format = output_format
        self.cpu_count = cpu_count
        self.preview = preview
        self.force_cpu_count = force_cpu_count
        self.extract_all = extract_all

    def extract(self, video_file, output_path, window_size_ms, target_frame_count: int = -1):
        start_time = time.time()
        vidcap = cv2.VideoCapture(video_file)
        #output_path = Path(video_file).stem

        success, frame = vidcap.read()

        # prepare paths
        if not os.path.exists(output_path) and not self.preview:
            os.makedirs(output_path)

        # prepare vars
        fps = vidcap.get(cv2.CAP_PROP_FPS)
        frame_count = int(vidcap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_length_ms = frame_count / float(fps) * 1000

        # calculate window if frame_count is set
        if target_frame_count > 0:
            window_size_ms = video_length_ms / target_frame_count
            print("set window size to %.2fms to create %d frames!" % (window_size_ms, target_frame_count))

        # option to extract all the frames
        if self.extract_all:
            window_size_ms = video_length_ms / frame_count
            print("extracting all %d frames!" % frame_count)

        step_count = math.floor(video_length_ms / window_size_ms)

        print("Video '%s' with %d FPS and %d frames (%.2fs) resulting in %d stills"
              % (os.path.basename(video_file), fps, frame_count, video_length_ms / 1000, step_count))

        if self.preview:
            print("Sharp Frame Extractor running in preview mode!")
            exit(0)

        # create windows
        windows = []
        for i in range(0, step_count):
            window_start_ms = i * window_size_ms
            window_end_ms = window_start_ms + window_size_ms

            # check if it is last window
            if i == step_count - 1:
                window_end_ms = video_length_ms

            windows.append((i, window_start_ms, window_end_ms))
        vidcap.release()

        # define buffer size
        buffer_size = math.ceil(frame_count / len(windows) * 1.5)

        # calculate max processor count (by default take 25% of CPU's)
        processor_count = max(1, min(round(self.cpu_count * 0.25), step_count))

        if self.force_cpu_count:
            processor_count = self.cpu_count

        # run multiprocessing
        print("Using a pool of %d CPU's with buffer size %d..." % (processor_count, buffer_size))
        results = []
        with Pool(processes=processor_count, initializer=init_worker,
                  initargs=((video_file,
                             output_path,
                             self.estimator,
                             self.crop_factor,
                             self.output_format,
                             self.min_sharpness,
                             buffer_size),)) as pool:
            for res in tqdm.tqdm(pool.imap_unordered(extract, windows), total=len(windows), desc="frame extraction"):
                if res is None:
                    continue
                name, sharpness = res
                results.append(name)

        end_time = time.time()

        frames = [result[0] for result in results if result is not None]

        print("Took %.4f seconds to extract %d frames!" % (end_time - start_time, len(windows)))
        return frames
