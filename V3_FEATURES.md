# V3 — Potential Features (out of scope for v2.x)

Everything here is **deliberately deferred** — out of scope for the current
v2.x line, parked for a possible v3. These are not bugs or open defects (those
live in `BACKLOG.md`); they are larger features or capability expansions, most
of which need a pipeline change rather than a localized fix.

Sourced from the old `BACKLOG.md` stretch goals (S1–S7), the v1 chemistry
stretch (P1), and the deferred items in `LIMITATIONS.md`.

Priority is rough intent, not commitment.

---

## Layout & routing

| # | Feature | Why deferred | Priority |
|---|---|---|---|
| V3-L1 | **Orthogonal / curved arrow routing** with entity avoidance. Pathway relations are straight bbox-edge-to-bbox-edge lines today, so an arrow can cross an unrelated node in a busy graph. | Needs a routing pass (channel/spline) in the layout engine. | Medium |
| V3-L2 | **Force-directed label placement** for dense pathways (replace the greedy relax-and-retry ladder). | Current placement degrades gracefully but isn't globally optimal. | Medium |
| V3-L3 | **Per-arrow conditional rendering in pathways** — different reagents/conditions per relation, as reaction layout already honors. | Schema supports `relation.conditions`; pathway layout doesn't draw them yet. | Low |

## Chemistry & molecular-structure rendering track (parked — not attempting in v2.x)

The whole chemistry-rendering deepening is deferred as one track. C3 is the
enabler the two arrow/structure items depend on; C1 is the pipeline rewrite at
the end.

| # | Feature | Why deferred | Priority |
|---|---|---|---|
| V3-C3 | **Per-element ids for `reaction_scheme`** groups so `convention_check` / `semantic_check` can audit each molecule, not just the composite `reaction_0` anchor. **Enabler** for C4/C5. | RDKit emits one composite SVG group today. | Medium |
| V3-C4 | **Curved mechanism arrows** (arrow-pushing) anchored on specific atoms. | Needs precise atom anchoring → depends on C3's per-element ids. | Low |
| V3-C5 | **Newman / chair projections** for conformational chemistry. | Specialized custom geometry outside the RDKit 2D path. | Low |
| V3-C1 | **True 3D ball-and-stick** chemistry rendering. Today `style="ball_stick"` is a 2D approximation (bigger atom labels, wider bonds, a visual lean). | Full 3D requires a rendering-pipeline rewrite; do last. | Low |
| V3-C2 | **3D protein structure integration** via a PyMOL handoff (ribbon/surface renders dropped into a panel). | Out of the vector-schematic scope; needs an external renderer bridge. | Low |

## Input & interoperability

| # | Feature | Why deferred | Priority |
|---|---|---|---|
| V3-I1 | **Import standardized pathway formats** (BioPAX / SBML / SBGN) → IR. | Large parser surface; needs a format→IR mapping spec. | Low |
| V3-I2 | **LaTeX / TikZ export** for direct manuscript inclusion. | New exporter backend alongside SVG/PNG/PDF. | Low |

## Output & presentation

| # | Feature | Why deferred | Priority |
|---|---|---|---|
| V3-O1 | **Animated / multi-frame figures** (step-reveal builds for talks). | Needs a timeline/frame model on top of the static compositor. | Low |

## Styling & typography

| # | Feature | Why deferred | Priority |
|---|---|---|---|
| V3-S1 | **Automatic palette selection** keyed on entity-type mix. | Style presets are fixed today; auto-selection needs a heuristic. | Low |
| V3-S2 | **Extended glyph coverage** — superscript minus (U+207B) and other scientific glyphs the system cairo font lacks render as tofu; prefer ASCII today. | Font-embedding / glyph-substitution pass. | Low |

---

## How to use this file

- Items here are **future features**, not open bugs. A real defect in shipped
  behavior goes in `BACKLOG.md`.
- When v3 starts, promote chosen items into a `PLAN.md` for that milestone and
  delete their rows here as they land (git history keeps the record).
