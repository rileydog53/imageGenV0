# Backlog — rolling list of open issues

This file tracks **open** work only. When an item lands, its row is deleted —
git history and each version's PLAN.md write-up preserve the record. Active
**V2.1** layout/primitive work is tracked in `PLAN.md` (items LT1–LT9); this
file holds issues *outside* that plan plus longer-horizon stretch goals.

Priority: high = blocks reading/using the tool; medium = shows up in real
figures soon; low = polish / advanced use.

> History note: V1.0 + V1.1 (orthogonal routing, reagent labels) and Waves 1–7
> (L1–L24, R1–R6, V1, P2–P3, ST1–ST5) are complete — see git history. V2.1
> (LT1–LT10: ring + layered DAG layout, ALAP rank tightening, RNA + broken-DNA
> primitives, the legibility trio, the `complex` entity type, SKILL.md sync +
> scope-guard) is complete — landed 2026-05-26 / 2026-05-27.

---

## Open issues

### Primitives

| # | Item | Source | Priority |
|---|---|---|---|
| P1 | True 3D ball-and-stick chemistry rendering. v1's `style="ball_stick"` is 2D (larger atom labels, wider bonds, a visual 3D lean); full 3D requires a rendering-pipeline rewrite. | `chemistry.py:8`; `phase2-step6-chemistry.md` | Low (Stretch) |

---

## Stretch goals (post-V2.1, long-horizon)

| # | Item | Source |
|---|---|---|
| S1 | Force-directed label placement for dense pathways | ROADMAP, TODO.txt |
| S2 | Automatic palette selection based on entity types | ROADMAP, TODO.txt |
| S3 | "Compile from BioPAX" — accept standardized pathway formats as input | ROADMAP, TODO.txt |
| S4 | 3D protein structure integration via PyMOL handoff | ROADMAP, TODO.txt |
| S5 | Animated / multi-frame figures for presentations | TODO.txt |
| S6 | LaTeX export for direct manuscript inclusion | TODO.txt |
| S7 | Per-arrow conditional rendering in pathways (different conditions per relation; currently only honored in reaction layout) | derived from R5 + L4 |

---

## How to use this file

- **Open issues only.** When an item lands, delete its row — git history keeps
  the record, and the implementation belongs in the session's PLAN.md, not here.
- **Active V2.1 work** lives in `PLAN.md` (LT1–LT9). This file is for issues
  *outside* that plan plus stretch goals.
- **New work:** add a row in the right section in the same shape, with a
  priority. Don't bury decisions in module docstrings alone.
