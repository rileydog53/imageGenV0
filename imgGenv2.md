---
name: imageGen
description: Generate publication-style schematic scientific figures — pathway diagrams, reaction schemes, experimental workflows, cellular schematics, and mechanism cartoons — from a natural-language request. Use when the user asks to draw, diagram, or sketch a biological pathway or signalling cascade, a chemical reaction scheme, an experimental protocol workflow, a labelled cell schematic, or a reaction mechanism cartoon. Produces vector-first schematic figures (SVG/PNG/PDF) — not photorealistic images and not plots of real data.
---

## Environment

- **CLI:** `~/Desktop/.venv/bin/python -m imageGen`
- **Repo:** `~/Desktop/imageGen-v1.1/`
- **Output:** `~/Desktop/scratch/<slug>.png` (create dir if missing: `mkdir -p ~/Desktop/scratch`)

---

## Execute — in order, no narration

1. Classify archetype (one word from the table below)
2. Write `/tmp/imagegen_ir.json` using the IR schema below
   - `reaction_scheme` only: also write `/tmp/imagegen_smiles.json`
3. Run CLI:
   ```
   ~/Desktop/.venv/bin/python -m imageGen /tmp/imagegen_ir.json \
     -o ~/Desktop/scratch/<slug>.png --verify \
     [--smiles-map /tmp/imagegen_smiles.json]
   ```
4. Read the output PNG with the Read tool and display it inline; print the file path

**On non-zero exit:** read stderr → fix the IR → re-run once. If still failing, show the user the error verbatim.

---

## Archetypes

| archetype | use when | smiles_map required |
|-----------|----------|---------------------|
| `pathway` | signaling / regulatory networks | no |
| `reaction_scheme` | chemical transformations (metabolites) | yes |
| `workflow` | step-by-step experimental protocols | no |
| `cellular_schematic` | subcellular localization (entities in compartments) | no |
| `mechanism_cartoon` | reaction mechanism cartoons | no |

---

## IR schema (condensed)

```json
{
  "archetype": "<archetype>",
  "title": "<optional>",
  "style_preset": "cell_press",
  "entities": [
    {"id": "e1", "type": "<type>", "label": "<display name>"}
  ],
  "compartments": [
    {"id": "c1", "label": "<name>", "contains": ["e1"]}
  ],
  "relations": [
    {
      "source": "e1", "target": "e2",
      "type": "<relation_type>",
      "label": "<optional arrow label>",
      "conditions": {
        "reagents": ["<reagent>"],
        "solvent": "<optional>",
        "temperature": "<optional>",
        "notes": "<optional>"
      }
    }
  ]
}
```

**Entity types:** `protein`, `kinase`, `receptor`, `ligand`, `metabolite`, `gene`, `complex`, `process`, `step`

**Relation types:** `activates`, `inhibits`, `phosphorylates`, `binds`, `produces`, `consumes`, `generic`

**Rules:**
- All `id` values must be unique strings (no spaces)
- Relation `source`/`target` must reference existing entity `id`s
- Compartment `contains` must reference existing entity `id`s
- Leaf figure: use `entities`/`relations`/`compartments` (no `panels`)
- Multi-panel: use `panels` list (no top-level entities/relations)

---

## smiles_map (reaction_scheme only)

```json
{"<entity_id>": "<SMILES string>", ...}
```

Use standard SMILES. If a SMILES is unknown, use a reasonable approximation or omit the entry (the entity will render as a text box).
