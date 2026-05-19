# Known Limitations (v1.0)

imageGen v1 produces journal-style figures for the five supported archetypes,
but it is deliberately scoped. The limitations below are known and accepted
for v1 — they are tracked for v2 in [BACKLOG.md](BACKLOG.md). If a figure
comes out wrong because of one of these, log it in [FEEDBACK.md](FEEDBACK.md).

## Label placement overflows on dense figures

Automatic label placement is **greedy**: for each label it picks the first
candidate position that does not collide with an entity primitive. On dense
figures it can run out of candidates and raise `LabelPlacementError` rather
than overlap labels.

Three checked-in fixtures hit this — `graphical_abstract_mrna_vaccine`,
`mechanism_cartoon`, `western_blot_schematic`. They render cleanly with
`labels=False` (CLI: `--no-labels`). A force-directed retry / leader-line
fallback is the planned v2 fix (BACKLOG L2, L14).

*Workaround:* render with labels suppressed, or reduce entity count.

## ~20-entity practical ceiling per figure

Layout engines place entities on a single band/row per compartment with no
wrapping. Beyond roughly 20 entities a figure becomes cramped and label
placement is far more likely to overflow. There is no hard cap — the figure
just degrades. Split large pathways across panels.

## Straight pathway arrows only

Pathway relations are drawn as straight arrows between entity bbox edges.
There is no orthogonal routing or curved-arrow avoidance, so an arrow can
cross an unrelated entity in a busy layout. Curved/routed arrows are a v2
item.

## No 3D structures

imageGen draws 2D schematic primitives only. Protein structures, ribbon
diagrams, and 3D molecular renderings are out of scope — a planned v2
stretch goal is a PyMOL handoff.

## Superscript / special-glyph coverage

Entity labels are rendered with the system font via cairo. Characters the
font lacks render as a missing-glyph box (tofu). Notably **superscript minus
(U+207B)** — common in mechanism labels like `Nu⁻` / `LG⁻` — is not covered;
the en-dash (U+2013) and most common scientific symbols are. Prefer ASCII
(`Nu-`, `LG-`) or a covered Unicode minus where possible.

## Reaction schemes are composite

A `REACTION_SCHEME` renders as one composite `reaction_0` SVG group with no
per-element ids. The `convention_check` verifier therefore skips per-entity
shape checks for reactions, and `semantic_check` verifies the single
composite anchor rather than each molecule.
