> 2026-09-13 当前路线已改为 [模型标注与独立审计](MODEL_ANNOTATION_PROTOCOL.md)，无需人类填写或核验。以下保留为历史/可选人工协议，不代表当前阻塞项。

# HUMAN ANNOTATION PROTOCOL

Status: **HUMAN_VALIDATION_REQUIRED** — this pack is generated, not labeled.

## Goal

Estimate agreement between structurally weak section labels (Positive_Review / Negative_Review keyword-gated aspects) and human aspect-polarity judgments. This is **not** gold accuracy of the production system until labels exist.

## Items

See `outputs/autonomous/wave1/human_annotation_pack_manifest.json`.
Texts live only in the gitignored private pack.

## Task

For each item, the annotator sees: city, aspect name, review **section** excerpt (already gated as mentioning the aspect).

Labels:
- `positive` / `negative` / `neutral` / `not_about_aspect`

Do **not** use the Booking overall score. Do **not** infer hotel identity beyond the excerpt.

## Quality

Double-annotate a 20% overlap subset. Report Cohen's kappa between annotators before comparing to weak labels.

## What this can / cannot claim

Can: measurement-error bound for weak labels.
Cannot: "ABSA gold accuracy"; causal service quality; manager intervention.
