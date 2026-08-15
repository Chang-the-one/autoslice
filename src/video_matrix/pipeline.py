from __future__ import annotations

from pathlib import Path
import yaml

from .ffmpeg_tool import FFmpegTool
from .frames import extract_keyframes
from .minimax_client import MiniMaxClient
from .models import EditPlan, Recipe, SceneAnalysis, SceneSemantic, Segment
from .planner import compile_plan, rules_select
from .scene_detect import detect_segments
from .transcribe import attach_transcript, transcribe
from .utils import read_json, sha256_file, write_json


class Pipeline:
    def __init__(self, cache_root: Path = Path("cache")) -> None:
        self.cache_root = cache_root

    def cache_dir(self, video: Path) -> tuple[str, Path]:
        digest = sha256_file(video)
        return digest, self.cache_root / digest

    def analyze(
        self,
        video: Path,
        *,
        force: bool = False,
        do_transcribe: bool = False,
        whisper_model: str = "small",
        threshold: float = 27.0,
        batch_size: int = 6,
        show_progress: bool = False,
    ) -> Path:
        digest, cache = self.cache_dir(video)
        analysis_path = cache / "scenes.json"
        if analysis_path.exists() and not force:
            return analysis_path

        cache.mkdir(parents=True, exist_ok=True)
        raw_path = cache / "segments.json"
        if raw_path.exists() and not force:
            segments = [Segment.model_validate(x) for x in read_json(raw_path)]
            if do_transcribe and not any(s.speech for s in segments):
                spans = transcribe(video, whisper_model)
                segments = attach_transcript(segments, spans)
                write_json(raw_path, [s.model_dump() for s in segments])
        else:
            segments = detect_segments(
                video, threshold=threshold, show_progress=show_progress,
            )
            if not segments:
                raise RuntimeError(
                    "No segments detected. Try a lower --threshold or check the video."
                )
            if do_transcribe:
                spans = transcribe(video, whisper_model)
                segments = attach_transcript(segments, spans)
            segments = extract_keyframes(video, segments, cache / "frames")
            write_json(raw_path, [s.model_dump() for s in segments])

        client = MiniMaxClient()
        semantics: list[SceneSemantic] = []
        partial_path = cache / "scenes.partial.json"
        done: dict[int, SceneSemantic] = {}
        if partial_path.exists() and not force:
            for row in read_json(partial_path).get("scenes", []):
                scene = SceneSemantic.model_validate(row)
                done[scene.segment_id] = scene

        pending = [s for s in segments if s.segment_id not in done]
        semantics.extend(done.values())
        if pending:
            print(f"Classifying {len(pending)} segments via MiniMax (resumable)...")
        for i in range(0, len(pending), batch_size):
            batch = pending[i : i + batch_size]
            result = client.classify_batch(batch)
            semantics.extend(result)
            semantics.sort(key=lambda x: x.segment_id)
            write_json(partial_path, {"scenes": [s.model_dump() for s in semantics]})

        analysis = SceneAnalysis(
            source_video=str(video.resolve()),
            source_hash=digest,
            scenes=sorted(semantics, key=lambda x: x.segment_id),
        )
        write_json(analysis_path, analysis.model_dump())
        return analysis_path

    def load_analysis(self, video: Path) -> tuple[Path, SceneAnalysis]:
        # 0. Direct cache hit (hash matches)
        _, cache = self.cache_dir(video)
        path = cache / "scenes.json"
        if path.exists():
            return path, SceneAnalysis.model_validate(read_json(path))
        # 1. Stem alias -> hash lookup. Created by analyze() so that a proxy
        #    analysis is reachable from the symlinked/original path too.
        for cand_path in (video, video.resolve(strict=False)):
            alias = self.cache_root / "aliases" / (cand_path.stem + ".json")
            if alias.exists():
                try:
                    digest = read_json(alias).get("digest")
                except Exception:
                    digest = None
                if digest:
                    aliased = self.cache_root / digest / "scenes.json"
                    if aliased.exists():
                        return aliased, SceneAnalysis.model_validate(read_json(aliased))
        # Fallback: scan sibling cache dirs for a scenes.json whose source_video
        # ends with the same filename as the requested video. Useful when
        # analysis was run on a proxy/transcoded copy but render targets the
        # original (timestamps are in seconds, so they remain valid).
        # Symlinks resolve() to the target, so also collect candidates by the
        # original input path components.
        target_stem = video.stem  # may be the symlink target stem
        target_name = video.name
        # Also consider the unresolved input: useful when the symlink target
        # has a different (e.g. localized) filename than the link itself.
        try:
            link = Path(video).resolve(strict=False)  # noqa: F841
        except Exception:
            pass
        best: tuple[int, Path, dict] | None = None
        # Build a candidate set of stems/names from the requested path (resolved and as-given).
        alt_stems: set[str] = set()
        alt_names: set[str] = set()
        for cand_path in (video, Path(str(video)).resolve(strict=False)):
            try:
                alt_stems.add(cand_path.stem)
                alt_names.add(cand_path.name)
            except Exception:
                continue
        for sibling in sorted(self.cache_root.iterdir()):
            if not sibling.is_dir():
                continue
            cand = sibling / "scenes.json"
            if not cand.exists():
                continue
            try:
                data = read_json(cand)
            except Exception:
                continue
            src_v = str(data.get("source_video", ""))
            score = 0
            if (src_v.endswith("/" + target_name) or src_v.endswith(target_name)
                    or Path(src_v).name in alt_names):
                score = 100  # exact filename match
            else:
                src_stem = Path(src_v).stem
                # match against request stem OR resolved-target stem OR vice versa
                stems_to_try = alt_stems | {target_stem}
                for stem in stems_to_try:
                    if stem and (src_stem.startswith(stem) or stem.startswith(src_stem)):
                        score = max(score, 50)
                        break
            if score and (best is None or score > best[0]):
                best = (score, cand, data)
        if best:
            _, cand, data = best
            return cand, SceneAnalysis.model_validate(data)
        raise FileNotFoundError(f"No semantic analysis found. Run: video-matrix analyze {video}")

    @staticmethod
    def load_recipe(recipes_path: Path, recipe_name: str) -> Recipe:
        data = yaml.safe_load(recipes_path.read_text(encoding="utf-8")) or {}
        if recipe_name not in data:
            raise KeyError(f"Recipe '{recipe_name}' not found in {recipes_path}")
        return Recipe.model_validate(data[recipe_name])

    def make_plan(
        self,
        video: Path,
        recipe_name: str,
        recipes_path: Path,
        planner: str,
    ) -> tuple[EditPlan, Path]:
        _, analysis = self.load_analysis(video)
        recipe = self.load_recipe(recipes_path, recipe_name)
        if planner == "ai":
            ids = MiniMaxClient().plan(analysis.scenes, recipe_name, recipe)
        elif planner == "rules":
            ids = rules_select(analysis.scenes, recipe)
        else:
            raise ValueError("planner must be 'ai' or 'rules'")

        plan = compile_plan(
            analysis.scenes, recipe_name, recipe, ids,
            planner=planner,
        )
        _, cache = self.cache_dir(video)
        plan_path = cache / f"edit_plan.{recipe_name}.{planner}.json"
        write_json(plan_path, plan.model_dump())
        return plan, plan_path

    def render(
        self,
        video: Path,
        plan: EditPlan,
        output: Path,
        *,
        max_width: int = 0,
        encoder: str = "auto",
    ) -> None:
        FFmpegTool().render(video, plan, output, max_width=max_width, encoder=encoder)
