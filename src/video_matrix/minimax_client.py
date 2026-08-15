from __future__ import annotations

import base64
import re
import json
import os
import time
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv
from openai import OpenAI

from .models import EditPlan, Recipe, SceneSemantic, Segment
from .utils import extract_json_object

CATEGORIES = [
    "garden", "harvest", "washing", "prep", "cutting",
    "cooking", "plating", "eating", "talking", "other",
]




def _parse_segment_id(raw) -> int | None:
    """Coerce model output like 25, "25", "SEGMENT 25", "seg-25" into an int.
    Returns None when no integer can be extracted."""
    if raw is None:
        return None
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        m = re.search(r"\d+", raw)
        if m:
            try:
                return int(m.group(0))
            except ValueError:
                return None
    return None

def _data_url(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


class MiniMaxClient:
    def __init__(self) -> None:
        load_dotenv()
        key = os.getenv("MINIMAX_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("Set MINIMAX_API_KEY in .env or the environment.")
        self.model = os.getenv("MINIMAX_MODEL", "MiniMax-M3")
        self.client = OpenAI(
            api_key=key,
            base_url=os.getenv("MINIMAX_BASE_URL", "https://api.minimax.io/v1"),
        )

    def _create(self, messages, *, max_tokens: int = 5000, retries: int = 3) -> str:
        last_exc: Exception | None = None
        for attempt in range(retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_completion_tokens=max_tokens,
                    temperature=0.1,
                    extra_body={"thinking": {"type": "disabled"}},
                )
                return response.choices[0].message.content or ""
            except Exception as exc:  # SDK/API errors vary by release.
                last_exc = exc
                if attempt + 1 < retries:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"MiniMax request failed after {retries} attempts: {last_exc}") from last_exc

    def classify_batch(self, segments: list[Segment]) -> list[SceneSemantic]:
        instructions = f"""
You are classifying short segments from an already-edited social video.
Each segment has two ordered representative frames and may have aligned speech text.
Return ONLY one JSON object with key \"segments\". Do not use markdown.

For every input segment return exactly:
segment_id, primary_category, labels, description, visual_quality, keep_score.

primary_category MUST be one of: {', '.join(CATEGORIES)}.
labels: concise open-ended semantic tags for action, object/ingredient, location, and shot type.
description: one factual sentence describing what is visibly happening.
visual_quality: 0..1, judging clarity/composition/usability as social footage.
keep_score: 0..1, judging how useful/distinct the segment is for a topical rough cut.
Do not infer events that are not visible. Use speech as supporting context, not as a substitute for the image.
Return each row with `segment_id` as a JSON integer (no quotes, no "SEGMENT" prefix) drawn from the `id=` values above.
""".strip()

        content: list[dict] = [{"type": "text", "text": instructions}]
        for seg in segments:
            content.append({
                "type": "text",
                "text": f"id={seg.segment_id} | {seg.start:.3f}-{seg.end:.3f}s | speech={json.dumps(seg.speech, ensure_ascii=False)} | FRAME A follows",
            })
            content.append({"type": "image_url", "image_url": {"url": _data_url(Path(seg.frame_paths[0])), "detail": "low"}})
            content.append({"type": "text", "text": f"id={seg.segment_id} | FRAME B follows"})
            content.append({"type": "image_url", "image_url": {"url": _data_url(Path(seg.frame_paths[1])), "detail": "low"}})

        raw = self._create([{"role": "user", "content": content}], max_tokens=max(2500, len(segments) * 500))
        obj = extract_json_object(raw)
        rows = obj.get("segments")
        if not isinstance(rows, list):
            raise ValueError("MiniMax JSON must contain a 'segments' array")

        by_id = {s.segment_id: s for s in segments}
        out: list[SceneSemantic] = []
        seen: set[int] = set()
        for row in rows:
            sid = _parse_segment_id(row.get("segment_id"))
            if sid is None or sid not in by_id or sid in seen:
                continue
            src = by_id[sid]
            try:
                row = {k: v for k, v in row.items() if k in SceneSemantic.model_fields}
                row.update(start=src.start, end=src.end, speech=src.speech)
                out.append(SceneSemantic.model_validate(row))
                seen.add(sid)
            except Exception as exc:  # noqa: BLE001
                print(f"  skip segment {sid}: {exc}")

        missing = [s.segment_id for s in segments if s.segment_id not in seen]
        if missing:
            print(f"  classified {len(seen)}/{len(segments)}; retrying {len(missing)} malformed/missing")
            # Re-attempt: re-issue API call just for missing ids.
            retry = [s for s in segments if s.segment_id not in seen]
            retry_semantics = self.classify_batch(retry)
            out.extend(retry_semantics)
            seen.update(s.segment_id for s in retry_semantics)
            still_missing = [s.segment_id for s in segments if s.segment_id not in seen]
            if still_missing:
                raise ValueError(f"MiniMax classification omitted segment IDs after retry: {still_missing}")
        return sorted(out, key=lambda x: x.segment_id)

    def plan(self, scenes: list[SceneSemantic], recipe_name: str, recipe: Recipe) -> list[int]:
        scene_rows = [
            {
                "segment_id": s.segment_id,
                "start": s.start,
                "end": s.end,
                "duration": round(s.duration, 3),
                "primary_category": s.primary_category,
                "labels": s.labels,
                "description": s.description,
                "visual_quality": s.visual_quality,
                "keep_score": s.keep_score,
                "speech": s.speech,
            }
            for s in scenes
        ]
        prompt = f"""
You are a rough-cut planner. You do NOT execute video commands.
Choose segment IDs from the semantic scene map to make one coherent social-video rough cut.
Return ONLY JSON: {{"segment_ids":[1,2,3],"rationale":"short explanation"}}.
Never invent IDs. Avoid redundant near-duplicate shots. Prefer strong visible actions and payoff shots.
Respect max_duration. Aim near target_duration but do not pad weak footage.
If preserve_source_order is true, return IDs in ascending source order.

Recipe name: {recipe_name}
Recipe: {recipe.model_dump_json()}
Additional recipe intent: {recipe.prompt or '(none)'}
Scene map: {json.dumps(scene_rows, ensure_ascii=False)}
""".strip()
        raw = self._create([{"role": "user", "content": prompt}], max_tokens=2500)
        obj = extract_json_object(raw)
        ids = obj.get("segment_ids", [])
        if not isinstance(ids, list):
            raise ValueError("Planner must return segment_ids as an array")
        return [int(x) for x in ids]
