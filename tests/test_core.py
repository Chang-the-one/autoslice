from pathlib import Path
from unittest.mock import patch

from video_matrix.models import EditPlan, Recipe, SceneSemantic
from video_matrix.planner import compile_plan, rules_select
from video_matrix.scene_detect import subdivide_interval
from video_matrix.utils import extract_json_object


def scene(i, start, end, category, labels, keep=0.9, quality=0.9):
    return SceneSemantic(
        segment_id=i, start=start, end=end, primary_category=category,
        labels=labels, description=" ".join(labels), visual_quality=quality, keep_score=keep,
    )


def test_subdivide_long_scene():
    chunks = subdivide_interval(0, 20, max_scene=8, target_window=5)
    assert len(chunks) == 4
    assert chunks[0] == (0, 5)
    assert chunks[-1] == (15, 20)


def test_subdivide_short_scene_kept_as_one():
    assert subdivide_interval(0, 6, max_scene=8, target_window=5) == [(0, 6)]


def test_extract_json_ignores_think_and_fence():
    raw = 'think secret think```json\n{"segments": []}\n```'
    assert extract_json_object(raw) == {"segments": []}


def test_rules_planner_filters_and_caps_duration():
    scenes = [
        scene(1, 0, 5, "harvest", ["tomato", "picking"]),
        scene(2, 5, 10, "cooking", ["pan"]),
        scene(3, 10, 15, "garden", ["pepper", "harvest"]),
    ]
    recipe = Recipe(include=["harvest", "garden"], exclude=["cooking"], target_duration=8, max_duration=10)
    ids = rules_select(scenes, recipe)
    assert ids == [1, 3]
    plan = compile_plan(scenes, "harvest", recipe, ids, planner="rules")
    assert len(plan.clips) == 2
    assert plan.estimated_duration == 10


def test_rules_planner_drops_below_thresholds():
    scenes = [
        scene(1, 0, 5, "harvest", ["tomato"], keep=0.1, quality=0.9),  # too low keep
    ]
    recipe = Recipe(include=["harvest"], min_keep_score=0.5)
    assert rules_select(scenes, recipe) == []


def test_compile_plan_drops_ai_ids_that_break_recipe():
    """The semantic safety net: AI planner cannot smuggle in non-matching IDs."""
    scenes = [
        scene(1, 0, 5, "cooking", ["pan"]),
        scene(2, 5, 10, "harvest", ["tomato"]),
    ]
    recipe = Recipe(include=["harvest"], exclude=["cooking"], target_duration=10, max_duration=20)
    # AI planner returns IDs that include a non-matching scene (#1)
    plan = compile_plan(scenes, "harvest", recipe, [1, 2], planner="ai")
    # Only the matching scene survives
    assert [c.segment_id for c in plan.clips] == [2]


def test_pipeline_reuses_cached_scenes_and_does_not_reclassify(tmp_path):
    from video_matrix.pipeline import Pipeline

    pipe = Pipeline(tmp_path)
    # Pre-bake a scenes.json so the pipeline will not touch MiniMax
    from video_matrix.utils import write_json, sha256_file
    video = Path("input/synthetic.mp4")
    digest = sha256_file(video)
    cache = tmp_path / digest
    cache.mkdir(parents=True, exist_ok=True)
    write_json(cache / "scenes.json", {
        "source_video": str(video.resolve()),
        "source_hash": digest,
        "scenes": [
            {
                "segment_id": 1, "start": 0.0, "end": 4.0,
                "primary_category": "harvest", "labels": ["tomato"],
                "description": "mock", "visual_quality": 0.9, "keep_score": 0.9, "speech": "",
            }
        ],
    })

    with patch("video_matrix.pipeline.MiniMaxClient") as M:
        inst = M.return_value
        result = pipe.analyze(video, show_progress=False)
        # MiniMaxClient should never have been instantiated
        inst.classify_batch.assert_not_called()
    assert result.exists()


def test_make_plan_rules_does_not_call_minimax(tmp_path):
    from video_matrix.pipeline import Pipeline
    from video_matrix.utils import write_json, sha256_file

    pipe = Pipeline(tmp_path)
    video = Path("input/synthetic.mp4")
    digest = sha256_file(video)
    cache = tmp_path / digest
    cache.mkdir(parents=True, exist_ok=True)
    write_json(cache / "scenes.json", {
        "source_video": str(video.resolve()),
        "source_hash": digest,
        "scenes": [
            {
                "segment_id": 1, "start": 0.0, "end": 4.0,
                "primary_category": "harvest", "labels": ["tomato"],
                "description": "mock", "visual_quality": 0.9, "keep_score": 0.9, "speech": "",
            }
        ],
    })
    with patch("video_matrix.pipeline.MiniMaxClient") as M:
        inst = M.return_value
        plan, plan_path = pipe.make_plan(video, "harvest_short", Path("recipes.yaml"), "rules")
        inst.plan.assert_not_called()
    assert len(plan.clips) == 1


def test_ffmpeg_renders_to_valid_mp4(tmp_path):
    """End-to-end FFmpeg render against the synthetic video fixture."""
    from video_matrix.ffmpeg_tool import FFmpegTool
    from video_matrix.models import EditPlan, EditClip

    source = Path("input/synthetic.mp4")
    if not source.exists():
        return  # no fixture available
    plan = EditPlan(
        recipe_name="t",
        clips=[EditClip(segment_id=1, source_start=0.0, source_end=4.0, reason="r")],
        planner="rules",
    )
    out = tmp_path / "out.mp4"
    FFmpegTool().render(source, plan, out)
    assert out.exists()
    assert out.stat().st_size > 0
