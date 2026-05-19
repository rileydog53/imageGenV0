# Worked Examples

One rendered figure per archetype, ordered by complexity. Each is produced
from a checked-in fixture in `tests/fixtures/` through the public
`render_figure` pipeline. Regenerate them all with:

```bash
~/Desktop/.venv/bin/python references/examples/generate_examples.py
```

| File | Archetype | Fixture | Shows |
|------|-----------|---------|-------|
| `01_reaction_scheme.png` | REACTION_SCHEME | `simple_reaction.json` | Fischer esterification — RDKit molecule rendering, reaction arrow with conditions above/below. |
| `02_pathway.png` | PATHWAY | `simple_activation.json` | The minimal pathway: two protein nodes, one activation arrow. |
| `03_mechanism_cartoon.png` | MECHANISM_CARTOON | `mechanism_cartoon.json` | A nucleophilic-substitution mechanism — entity nodes with reaction arrows. Rendered with `labels=False` (this fixture overflows the greedy label engine). |
| `04_cellular_schematic.png` | CELLULAR_SCHEMATIC | `cellular_schematic.json` | Compartment bands (extracellular → membrane → cytoplasm → nucleus → mitochondrion) with entities placed by location. |
| `05_workflow.png` | WORKFLOW | `three_panel_workflow.json` | A three-panel experimental workflow (treat → lyse → blot), the most structurally complex archetype. |

See `../../LIMITATIONS.md` for known rendering caveats (label overflow on
dense figures, superscript-glyph coverage, entity ceiling).
