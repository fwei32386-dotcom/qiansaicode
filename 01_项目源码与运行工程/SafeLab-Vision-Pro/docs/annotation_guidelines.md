# Annotation Guidelines

This project uses YOLO detection labels:

```text
class_id x_center y_center width height
```

All coordinates are normalized to image width and height.

## Classes

```text
0 person
1 helmet
2 vest
3 fire
4 smoke
```

## General Rules

- Draw tight boxes around visible object boundaries.
- Keep one object per line in the label file.
- Do not label uncertain objects if the class cannot be identified.
- Keep partially occluded objects if at least about 30% is visible.
- Do not use polygon, segmentation, or rotated boxes for the first baseline.

## Person

Label the visible full body area of each person.

- Include head, torso, arms, and legs when visible.
- If only upper body is visible, box the visible person area.
- Do not label mannequins, posters, or screen images as person.

## Helmet

Label the helmet itself, not the full head.

- Hard hats and safety helmets are `helmet`.
- Ordinary caps are not `helmet`.
- If helmet is mostly hidden, skip it unless clearly visible.

## Vest

Label the visible safety vest or reflective vest area.

- Do not label ordinary shirts as `vest`.
- If a lab coat is added later, it should be a separate class, not `vest`.

## Fire

Label visible flame regions.

- Include flame body, not the whole smoke cloud.
- Do not label red warning lights or reflections as fire.

## Smoke

Label visible smoke plume or smoke region.

- Smoke is often fuzzy; use a reasonable tight rectangle around the visible plume.
- Do not label normal shadows or mild blur as smoke.
- Steam/fog should be kept as negative examples unless the project decides to treat them as smoke.

## Split Rules

Recommended first split:

```text
train: 70%
val: 20%
test: 10%
```

Keep similar frames from the same video or same scene in the same split to avoid evaluation leakage.
