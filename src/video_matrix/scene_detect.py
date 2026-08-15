from __future__ import annotations

import math
from pathlib import Path

from scenedetect import ContentDetector, detect

from .models import Segment


def subdivide_interval(start: float, end: float, *, max_scene: float = 8.0, target_window: float = 5.0) -> list[tuple[float, float]]:
    duration = end - start
    if duration <= max_scene:
        return [(start, end)]
    parts = max(2, math.ceil(duration / target_window))
    width = duration / parts
    return [(start + i * width, start + (i + 1) * width) for i in range(parts)]


def detect_segments(
    video_path: Path,
    *,
    threshold: float = 27.0,
    max_scene: float = 8.0,
    target_window: float = 5.0,
    min_segment_duration: float = 0.25,
    show_progress: bool = False,
) -> list[Segment]:
    scene_list = detect(
        str(video_path),
        ContentDetector(threshold=threshold),
        show_progress=show_progress,
    )
    if not scene_list:
        raise RuntimeError("No scene intervals were returned by PySceneDetect.")

    intervals: list[tuple[float, float]] = []
    for start_tc, end_tc in scene_list:
        intervals.extend(
            subdivide_interval(
                start_tc.get_seconds(), end_tc.get_seconds(),
                max_scene=max_scene, target_window=target_window,
            )
        )

    return [
        Segment(segment_id=i + 1, start=round(s, 3), end=round(e, 3))
        for i, (s, e) in enumerate(intervals)
        if e - s >= min_segment_duration
    ]
