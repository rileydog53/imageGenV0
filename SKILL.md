---
name: imageGen
description: Generate publication-style schematic scientific figures — pathway diagrams, reaction schemes, experimental workflows, cellular schematics, and mechanism cartoons — from a natural-language request. Use when the user asks to draw, diagram, or sketch a biological pathway or signalling cascade, a chemical reaction scheme, an experimental protocol workflow, a labelled cell schematic, or a reaction mechanism cartoon. Produces vector-first schematic figures (SVG/PNG/PDF) — not photorealistic images and not plots of real data.
---

# imageGen — Scientific Figure Generation

Generate publication-style schematic figures — pathway diagrams, reaction
schemes, experimental workflows, cellular schematics, mechanism cartoons, and
multi-panel graphical abstracts — from a natural-language request.

Figures are **vector-first and schematic**: clean SVG/PNG/PDF assembled from a
curated library of biology- and chemistry-aware primitives. This is not an
image generator and not a data-plotting tool.

---

## Setup — environment & paths

imageGen is an installed Python package; commands in this skill must run
through its virtualenv and reference absolute paths, since the skill may be
invoked from any working directory:

- **Python:** use `~/Desktop/.venv/bin/python`, never bare `python`. The
  `imageGen` package is installed there — both `python -m imageGen` (CLI) and
  `from imageGen... import` (validation/verification) resolve from it.
- **Repo root:** `~/Desktop/imageGen-v0.1/`. Where this skill cites
  `tests/fixtures/<file>` it means
  `~/Desktop/imageGen-v0.1/tests/fixtures/<file>` — read those as worked IR
  examples.
- **Working files:** write the IR JSON, any `smiles_map` JSON, and the
  rendered figure to the user's current working directory (or a path the user
  gives); use `~/Desktop/scratch/` for throwaway intermediates.

The render command in step 6, in absolute form:

```
~/Desktop/.venv/bin/python -m imageGen figure.json -o figure.png \
    --style nature --dpi 300
```

---

## When to trigger this skill

Use imageGen when the user asks for a **schematic scientific figure**:

- A signalling or metabolic **pathway** ("show the MAPK cascade", "diagram how
  insulin signalling works")
- A **reaction scheme** ("draw the oxidation of ethanol", "show this SN2 step")
- An experimental **workflow** ("a figure of the western blot protocol")
- A **cellular schematic** ("a labelled eukaryotic cell", "where these
  proteins localise")
- A **mechanism cartoon** ("cartoon the catalytic mechanism")
- A multi-panel **graphical abstract** combining the above

## When NOT to trigger

Decline (politely, see *Refusal scripts*) and suggest the right tool when the
user wants:

- A **photorealistic** image or artistic illustration — this skill draws
  schematics only.
- A **plot of real measured data** (bar chart, dose-response curve, kinetics)
  — use a plotting library on the actual dataset.
- A **3D molecular structure** — defer to PyMOL or a structure viewer.
- A figure whose request **cannot be classified** into one of the five
  archetypes below.

---

## Mandatory workflow

Follow these steps in order. Do not skip the IR or the verification step.

1. **Classify** the request into exactly one archetype (see *Archetypes*). If
   none fit, refuse.
2. **Extract** the figure into entities, compartments, and relations (or, for
   a multi-panel figure, panels). See *IR reference*.
3. **Write** the IR to a JSON file (e.g. `figure.json`).
4. **Validate** it before rendering:
   ```python
   from imageGen.ir.schema import Figure
   ir = Figure.model_validate_json(open("figure.json").read_text())
   ```
   A `pydantic.ValidationError` means the IR is malformed — read the message,
   fix the JSON, revalidate. Common causes: a relation referencing an unknown
   entity id, an entity `location` naming a missing compartment, or a figure
   that mixes top-level `entities` with `panels` (forbidden — see *IR reference*).
5. **For `reaction_scheme` figures only:** build a `smiles_map`,
   `{entity_id: "SMILES"}`, covering every entity. You supply the SMILES from
   chemical knowledge (e.g. ethanol → `"CCO"`). It is a render argument, not
   an IR field. Write it to its own JSON file for the CLI.
6. **Render** via the CLI:
   ```
   python -m imageGen figure.json -o figure.png [--style nature]
                         [--smiles-map smiles.json] [--dpi 300]
   ```
   A PNG/PDF render also writes a sibling `figure.svg` next to it — the
   verification step needs that SVG.
7. **Verify** the rendered SVG and surface any failure (fail loud — do not
   swallow the exception):
   ```python
   from imageGen.verify.semantic_check import semantic_check
   from imageGen.verify.legibility_check import legibility_check
   from imageGen.verify.convention_check import convention_check
   semantic_check(ir, "figure.svg")     # every IR element present?
   legibility_check("figure.svg")       # no overlapping / undersized labels?
   convention_check(ir, "figure.svg")   # inhibition T-bars, correct shapes?
   ```
   If a check raises, the figure has a real problem — fix the IR or the
   request and re-render rather than presenting a broken figure.
8. **Present** the figure to the user with a one- or two-sentence caption
   describing what it depicts. If any element is illustrative or schematic
   rather than measured data, say so explicitly in the chat text.

---

## Archetypes

| Archetype (`archetype` value) | Use for | Shape | Needs `smiles_map` |
|---|---|---|---|
| `pathway` | Signalling / regulatory networks: entities connected by typed relations, optionally grouped into compartments | Leaf | No |
| `reaction_scheme` | A chemical transformation: reactants → products with reagents/conditions | Leaf | **Yes** |
| `workflow` | Step-by-step experimental procedures | Leaf or panels | No |
| `cellular_schematic` | A cell with compartments and localised entities | Leaf | No |
| `mechanism_cartoon` | A reaction or process mechanism told as a cartoon | Leaf | No |

All five render. `workflow`, `cellular_schematic`, and `mechanism_cartoon`
route through the pathway layout engine. A multi-panel **graphical abstract**
is a `Figure` with `panels` — each panel's `content` is itself a `Figure` of
any archetype.

---

## IR reference

The IR (intermediate representation) is a `Figure` — a strict, validated
Pydantic model. Unknown fields are rejected. Build it as JSON.

### `Figure`

| Field | Type | Required | Notes |
|---|---|---|---|
| `archetype` | archetype value | yes | one of the five above |
| `title` | string | no | |
| `caption` | string | no | |
| `style_preset` | string | no | defaults to `"cell_press"` |
| `entities` | list of `Entity` | no* | |
| `compartments` | list of `Compartment` | no* | |
| `relations` | list of `Relation` | no* | |
| `panels` | list of `Panel` | no* | |
| `annotations` | list of `Annotation` | no | |

**\*Leaf-XOR-panel rule:** a figure is *either* a leaf (has
`entities`/`compartments`/`relations`) *or* multi-panel (has `panels`) —
never both.

### `Entity`

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | yes | unique within the figure |
| `type` | entity type | yes | see below |
| `label` | string | yes | shown on the figure |
| `location` | string | no | a compartment `id` (must exist) |
| `style` | object | no | per-entity style overrides |

`type` ∈ `protein`, `ligand`, `receptor`, `kinase`, `gene`, `metabolite`,
`cell`, `organelle`, `equipment`, `sample`, `generic`.

### `Compartment`

`id` (unique), `type`, `label`. `type` ∈ `extracellular`, `membrane`,
`cytoplasm`, `nucleus`, `mitochondrion`, `custom`.

### `Relation`

| Field | Type | Required | Notes |
|---|---|---|---|
| `source` | string | yes | an entity `id` (must exist) |
| `target` | string | yes | an entity `id` (must exist) |
| `type` | relation type | yes | see below |
| `label` | string | no | |
| `conditions` | `ReactionConditions` or object | no | reaction context |

`type` ∈ `activates`, `inhibits`, `binds`, `translocates`, `phosphorylates`,
`transcribes`, `generic`. Conventions: `activates` → solid arrow,
`inhibits` → T-bar.

### `ReactionConditions` (for `relation.conditions`)

`reagents` (list of strings), `yield_pct` (0–100), `reversible` (bool),
`notes` (string). All optional.

### `Panel` (multi-panel figures)

`id` (unique), `title` (optional), `content` (a nested `Figure`),
`grid` (`[row, col, rowspan, colspan]` — `row`/`col` ≥ 0, spans ≥ 1, panels
must not overlap).

### `Annotation`

`type` ∈ `label`, `caption`, `scale_bar`; `text` (string); `position` —
either `[x, y]` coordinates or a named slot ∈ `top`, `bottom`, `left`,
`right`, `top-left`, `top-right`, `bottom-left`, `bottom-right`, `center`.

### Validators (will reject the IR if violated)

- Entity, compartment, and panel `id`s are unique within a figure.
- Every `relation.source`/`target` references an existing entity.
- Every `entity.location` references an existing compartment.
- Leaf-XOR-panel (above). Panel grids must not overlap.

---

## Style presets

Pass `--style` (or `style_preset` in the IR) to pick a journal aesthetic:

- `cell_press` — soft, friendly, rounded. **Default.**
- `nature` — bolder, geometric, colorblind-safe palette.
- `acs` — monochrome, formal; the chemistry default.

---

## Refusal scripts

When a request falls outside scope, decline plainly and redirect:

- **Fabricated data plot** — "I can't generate a chart that looks like real
  measured data, since that would be misleading. imageGen produces
  schematic figures only. If you have an actual dataset I can help you plot
  it with a plotting library instead."
- **Photorealistic image** — "imageGen draws schematic, vector-style
  scientific figures, not photorealistic images. I can make a clean
  schematic of this if that works for you."
- **3D molecular structure** — "This skill renders 2D schematics. For a 3D
  molecular structure, a tool like PyMOL is the right choice."

---

## Pointers

- **Primitives** (`imageGen/primitives/`): proteins, membranes, nucleic
  acids, cells, chemistry (RDKit), lab equipment, arrows — assembled
  automatically by the layout engines; you author the IR, not primitives.
- **CLI** (`python -m imageGen`): `IR_PATH -o OUT` plus optional
  `--style {cell_press,nature,acs}`, `--format {svg,png,pdf}` (else inferred
  from the output suffix), `--dpi N` (default 300), `--smiles-map FILE.json`,
  `--no-labels`.
- **Example IRs**: every archetype has a worked example in
  `tests/fixtures/` — read these to pattern-match the JSON shape.

### Known limitation

Label placement is greedy. On dense figures it can raise
`LabelPlacementError`. If that happens: simplify the figure (fewer entities,
shorter labels), or render with `--no-labels` and describe the relations in
the caption instead.

---

## Cookbook

Worked examples — each `tests/fixtures/<file>` is a complete, validated IR.

1. **"Show the MAPK kinase cascade."** → `pathway`. Entities Ras (protein),
   Raf/MEK/ERK (kinases); relations `activates` then `phosphorylates`.
   See `tests/fixtures/mapk_cascade.json`. Render:
   `python -m imageGen tests/fixtures/mapk_cascade.json -o mapk.png`.

2. **"Diagram a GPCR signalling event across the membrane."** → `pathway`
   with compartments (`extracellular`, `membrane`, `cytoplasm`); entities
   carry `location`. See `tests/fixtures/gpcr_signaling.json`.

3. **"Draw how this drug inhibits its target."** → `pathway` with an
   `inhibits` relation (renders as a T-bar). See
   `tests/fixtures/drug_inhibition.json`.

4. **"Show the oxidation of ethanol to acetaldehyde."** → `reaction_scheme`.
   Two `metabolite` entities, one relation with `conditions`
   (`reagents`, `notes`). Build `smiles_map`
   `{"alcohol": "CCO", "aldehyde": "CC=O"}`. See
   `tests/fixtures/oxidation_reaction.json`. Render:
   `python -m imageGen tests/fixtures/oxidation_reaction.json -o rxn.png
   --smiles-map smiles.json`.

5. **"Cartoon the SN2 substitution mechanism."** → `mechanism_cartoon` with
   `binds`/`generic` relations and `acs` style. See
   `tests/fixtures/mechanism_cartoon.json`.

6. **"A labelled diagram of a eukaryotic cell."** → `cellular_schematic`
   with five compartments and entities localised via `location`. See
   `tests/fixtures/cellular_schematic.json`.

7. **"A three-step western blot workflow figure."** → multi-panel
   `workflow`: a `Figure` with three `panels` on a `[0,c,1,1]` grid, each
   panel's `content` a small `workflow` figure. See
   `tests/fixtures/three_panel_workflow.json`.

8. **"A graphical abstract for an mRNA vaccine study."** → multi-panel
   figure mixing `cellular_schematic` and `pathway` panels. See
   `tests/fixtures/graphical_abstract_mrna_vaccine.json`.
