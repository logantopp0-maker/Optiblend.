# OptiBlend

**Final V1 release · Blender 4.0+ · GPL-3.0-or-later**

OptiBlend is a Blender workflow add-on I built to make the first stages of Blender easier to understand without replacing Blender's normal tools. It started as a scene optimiser, then gradually grew into a guided workflow with drag-and-drop shapes, procedural materials, scene cleanup, progressive user modes and advanced pipeline checks.

The main idea is simple: **Beginner should feel clear, Intermediate should open Blender back up, and Advanced should stop holding the user back.**

> Development builds used internal version numbers through V1.23.1. **v1.0.0 is the first public Final V1 release.** The internal `v123` operator/class namespace is intentionally retained for stability.

## Quick start

1. Download `OptiBlend_v1.0.0_FINAL_V1.zip` from the release.
2. In Blender, open **Edit → Preferences → Add-ons** and use **Install from Disk / Install...** depending on your Blender version.
3. Select the ZIP and enable **OptiBlend**.
4. Open the 3D Viewport.
5. Press **Q** to open the OptiBlend Helper.

You do **not** need to unzip the release before installing it.

### Main shortcuts

| Key | Action |
| --- | --- |
| `Q` | Open / close the OptiBlend Helper |
| `G` | Move selected object |
| `R` | Rotate selected object |
| `S` | Scale selected object |
| `X / Y / Z` | Constrain movement / rotation / scale to an axis |
| `Tab` | Object Mode / Edit Mode |
| `F12` | Image render |
| `Ctrl + F12` | Animation render |
| `Numpad 0` | Camera view |
| `L` | Open the Test Lab (development/debug tool) |

## Modes

### Beginner

Beginner mode is deliberately small. It keeps the focus on placing objects, moving them correctly and learning actual Blender shortcuts.

- simplified workspace
- clear **PRESS Q = HELPER** prompt
- Shapes and Materials as the main creation tools
- Move tool enabled automatically
- ground/grid placement
- centred XYZ helper around the visible object, not an offset origin
- guided `G`, `R`, `S`, `Tab` and `X/Y/Z` commands
- friendlier Edit Mode snapping
- advanced pipeline tools hidden
- one main Outliner with the alternate side area used as a UV helper

### Intermediate

Intermediate is for users who are comfortable with Blender's basics and want more freedom without bringing every advanced tool back at once.

- more Blender workspaces
- normal modelling freedom
- modifiers
- lighting
- rendering and camera controls
- external model import
- scene scan / cleanup tools
- hover help still available

### Advanced

Advanced exposes the full OptiBlend workflow and the more technical tools.

- wider Blender workspace access
- Advanced OptiBlend sidebar
- QuadriFlow retopology
- non-destructive triangulation
- subdivision-ready setup
- topology audit
- Mixamo readiness checks
- modifier / particle / Geometry Nodes checks
- performance audit
- FBX / export preparation
- team collection setup
- UV helper
- weighted normals helper
- modifier-stack helper

## Shape placement

The Shapes shelf works more like an asset browser than Blender's standard Add menu.

- named shape thumbnails
- horizontal scrolling
- search
- drag into the viewport
- glowing placement preview
- ground, surface and centre snapping
- rotate while placing
- `Shift + wheel` for smaller rotation steps
- `Ctrl` for centre snapping
- `R` for a quick rotation step while dragging
- `Alt + R` to reset placement rotation

The library includes Cube, Sphere, Ico Sphere, Circle, Cylinder, Cone, Plane, Torus, Suzanne, Grid, Pyramid and Capsule.

## Materials

OptiBlend includes a searchable procedural material shelf. Presets are generated with Blender shader nodes and are intended as useful starting points rather than replacements for full texture libraries.

Categories include:

- Common Surfaces
- Fabrics & Textiles
- Natural Elements
- Man-made / Industrial
- Organic / Specialised
- OptiBlend / Beta

The **Custom** material uses Blender's native colour picker, so clicking the colour swatch opens the normal Blender colour wheel. Metal, Glow, Glass, Wood, Concrete, Marble, Leather, Velvet, Grass, Ice, Tech and other presets are also included.

## Modifiers

OptiBlend can add common non-destructive modelling modifiers directly from its workflow:

- Subdivision Surface
- Bevel
- Mirror
- Solidify
- Array

Advanced mode also includes retopology and modifier-stack helpers.

## Rendering and camera tools

The Render section keeps the common actions obvious:

- create / select camera
- camera view
- align camera to current view
- `F12` image render
- `Ctrl + F12` animation render
- Compositor Glow / Glare helper

## External model import

OptiBlend can import models through its own menu using Blender's built-in import operators.

Supported formats where the relevant Blender importer is available:

- FBX
- OBJ
- GLTF / GLB
- STL

After import, OptiBlend can keep the new objects selected, enable the Move tool, organise them into collections and report basic polygon / transform information.

## Mixamo readiness

The Advanced Rig Check gives a **heuristic** readiness report for character-export preparation. It can check measurable Blender data such as:

- object centring
- scale / rotation
- quads, triangles and ngons
- non-manifold geometry
- loose geometry
- disconnected mesh islands
- armature presence
- modifiers
- particle systems
- Geometry Nodes
- unrelated visible scene content

It **cannot** reliably decide whether a character has correct humanoid proportions or a genuinely neutral pose. Those remain manual checks. See [`MIXAMO_RESEARCH.md`](MIXAMO_RESEARCH.md) for the research and limitations.

## HCI / design decisions

The interface was developed around progressive disclosure, recognition over recall, clear status feedback, contextual help and user control. Feedback from Year 13 testing directly changed snapping, the Q Helper, drag visibility, retopology, import workflow and the beginner layout.

See [`HCI_REPORT.md`](HCI_REPORT.md) for the full design notes.

## Important limitations

This is a Final V1 release, but there are still a few areas worth knowing about:

- OptiBlend changes visible workspaces/editor areas when applying modes. If you use a heavily customised Blender startup layout, test the add-on in a copy of your setup first.
- Workspace restoration relies on Blender's workspace data and can behave differently with heavily customised startup files.
- External import support depends on the matching Blender importer being available in that Blender build.
- QuadriFlow can take time on dense meshes and changes topology. Duplicate important models before running destructive retopology operations.
- The Mixamo score is guidance, not a guarantee that Adobe Mixamo will accept or rig a character correctly.
- Procedural material presets are lightweight starting materials, not scanned/production texture assets.
- The Test Lab (`L`) is included for development and classroom testing. Normal users can ignore it.

## Project files

| File | Purpose |
| --- | --- |
| `__init__.py` | Main Blender add-on |
| `README.md` | Installation and user guide |
| `CHANGELOG.md` | Final V1 release notes |
| `HCI_REPORT.md` | HCI decisions and user-feedback implementation |
| `MIXAMO_RESEARCH.md` | Research behind the Advanced readiness checker |
| `FINAL_TESTING.md` | Manual regression checklist |
| `LICENSES.txt` | Third-party licences and research references |
| `LICENSE` / `COPYING` | GNU GPL v3 licence text |

## Licence

OptiBlend's Python add-on code is released under **GNU GPL v3 or later (GPL-3.0-or-later)** so it remains compatible with Blender's licensing requirements.

The included OptiBlend preview assets are listed in [`LICENSES.txt`](LICENSES.txt), together with the Blender, BlenderKit, Nielsen Norman Group and Adobe Mixamo references used during development.

## Author

**Logan Topp**

OptiBlend was developed as a student technology project and is now packaged as a usable Final V1 release for other students and Blender learners to test and use.
