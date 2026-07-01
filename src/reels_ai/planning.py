from __future__ import annotations

from dataclasses import asdict, dataclass

from .alignment import CaptionEvent


@dataclass
class SceneTiming:
    scene: int
    filename: str
    anchor: str
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


def equal_scene_timings(filenames: list[str], duration: float) -> list[SceneTiming]:
    if not filenames: return []
    step = duration / len(filenames)
    return [SceneTiming(i + 1, name, "Automatic", i * step, duration if i == len(filenames)-1 else (i+1)*step) for i, name in enumerate(filenames)]


def anchored_scene_timings(filenames: list[str], anchor_indices: list[int], events: list[CaptionEvent], duration: float) -> list[SceneTiming]:
    starts = [events[min(max(0, i), len(events)-1)].start for i in anchor_indices] if events else [0.0] * len(filenames)
    if starts: starts[0] = 0.0
    result = []
    for i, name in enumerate(filenames):
        end = starts[i + 1] if i + 1 < len(starts) else duration
        if end <= starts[i]: raise ValueError("Image anchors must be strictly ordered.")
        result.append(SceneTiming(i + 1, name, events[anchor_indices[i]].token if events else "", starts[i], end))
    return result


def validate_scene_timings(timings: list[SceneTiming], duration: float) -> None:
    if not timings: raise ValueError("At least one scene is required.")
    for i, scene in enumerate(timings):
        if scene.start < 0 or scene.end <= scene.start: raise ValueError(f"Scene {scene.scene} has an invalid duration.")
        if i and scene.start < timings[i-1].end - .001: raise ValueError("Scene timings overlap.")
    if abs(timings[-1].end - duration) > .05: raise ValueError("The final scene must reach the end of the voiceover.")


def timings_as_rows(timings: list[SceneTiming]) -> list[dict]:
    return [{**asdict(t), "duration": round(t.duration, 3)} for t in timings]

