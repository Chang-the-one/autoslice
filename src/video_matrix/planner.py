from __future__ import annotations

from .models import EditClip, EditPlan, Recipe, SceneSemantic


def _terms(scene: SceneSemantic) -> set[str]:
    words = {scene.primary_category.lower()}
    words.update(x.lower() for x in scene.labels)
    words.update(scene.description.lower().replace("/", " ").replace("-", " ").split())
    return words


def eligible(scene: SceneSemantic, recipe: Recipe) -> bool:
    if scene.keep_score < recipe.min_keep_score or scene.visual_quality < recipe.min_visual_quality:
        return False
    text = " ".join([scene.primary_category, *scene.labels, scene.description]).lower()
    if recipe.exclude and any(term.lower() in text for term in recipe.exclude):
        return False
    if recipe.include and not any(term.lower() in text for term in recipe.include):
        return False
    return True


def rules_select(scenes: list[SceneSemantic], recipe: Recipe) -> list[int]:
    candidates = [s for s in scenes if eligible(s, recipe)]
    candidates.sort(key=lambda s: (s.keep_score * 0.65 + s.visual_quality * 0.35), reverse=True)

    chosen: list[SceneSemantic] = []
    duration = 0.0
    for scene in candidates:
        if duration + scene.duration > recipe.max_duration + 0.001:
            continue
        chosen.append(scene)
        duration += scene.duration
        if duration >= recipe.target_duration:
            break
    if recipe.preserve_source_order:
        chosen.sort(key=lambda s: s.start)
    return [s.segment_id for s in chosen]


def compile_plan(
    scenes: list[SceneSemantic],
    recipe_name: str,
    recipe: Recipe,
    selected_ids: list[int],
    *,
    planner: str,
) -> EditPlan:
    scene_by_id = {s.segment_id: s for s in scenes}
    seen: set[int] = set()
    clips: list[EditClip] = []
    duration = 0.0

    for sid in selected_ids:
        if sid in seen or sid not in scene_by_id:
            continue
        scene = scene_by_id[sid]
        if not eligible(scene, recipe):
            continue
        if duration + scene.duration > recipe.max_duration + 0.001:
            continue
        clips.append(EditClip(
            segment_id=sid,
            source_start=scene.start,
            source_end=scene.end,
            reason=f"{scene.primary_category}: {scene.description}",
        ))
        seen.add(sid)
        duration += scene.duration

    if recipe.preserve_source_order:
        clips.sort(key=lambda c: c.source_start)
    return EditPlan(recipe_name=recipe_name, clips=clips, planner=planner)
