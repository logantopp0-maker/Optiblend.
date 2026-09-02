# OptiBlend Final V1 - Manual Test Checklist

## Startup / HCI
- [ ] Enable the add-on in a clean Blender file.
- [ ] Confirm Beginner starts with the intended simplified workspace.
- [ ] Confirm `PRESS Q = HELPER` is visible.
- [ ] Press Q to open the Helper and Q again to close it.
- [ ] Press L and confirm the Test Lab opens.

## Q Helper / hover UI
- [ ] Hover Shapes and confirm custom child cards appear.
- [ ] Confirm Import Model is available from the Shapes child tools.
- [ ] Hover Materials and test Colour Wheel / Metal / Glow.
- [ ] Hover Render and confirm Camera / Numpad 0 / Ctrl+Alt+0 / F12 / Ctrl+F12 / FX labels.
- [ ] Confirm child help text changes as each mini-tool is hovered.
- [ ] Change OptiBlend Menu Scale and confirm the custom UI scales.

## Shapes / snapping / XYZ
- [ ] Drag a cube to Grid.
- [ ] Drag a cylinder and rotate it onto its side.
- [ ] Test mouse wheel, Shift+wheel, R, Alt+R and X/Y/Z while dragging.
- [ ] Test Ctrl centre snap onto another object.
- [ ] Test surface snapping / rotation against another object.
- [ ] Confirm glowing placement outline is easy to see.
- [ ] Select a mesh with an offset origin and confirm XYZ appears around visible geometry.

## Edit Mode
- [ ] Press Tab to enter Edit Mode.
- [ ] Confirm Smart Snap applies useful mesh targets.
- [ ] Return to Object Mode and confirm object placement snapping still works.

## Materials
- [ ] Open Materials and use the native colour wheel.
- [ ] Drag several procedural materials onto objects.
- [ ] Test Metal and Glow.
- [ ] Search/filter the material library.

## Modifiers
- [ ] Add Subdivision Surface.
- [ ] Add Bevel.
- [ ] Add Mirror.
- [ ] Add Solidify.
- [ ] Add Array.

## Render / camera / compositor
- [ ] Create / select camera.
- [ ] Numpad 0 / Camera View works.
- [ ] Align Camera to View works.
- [ ] F12 image render works.
- [ ] Ctrl+F12 animation render works.
- [ ] Compositor Glow / Glare creates or updates one OptiBlend glare node.

## External import (Jia feedback)
- [ ] Import one FBX.
- [ ] Import one OBJ.
- [ ] Import one GLTF/GLB.
- [ ] Import one STL if the importer exists in this Blender build.
- [ ] Confirm imported objects are selected afterwards.
- [ ] Confirm Move tool is active afterwards.
- [ ] Test Auto Organise Imports on/off.
- [ ] Confirm import scan reports polygons / transform warning when enabled.

## Progressive modes
- [ ] Beginner hides advanced pipeline tools.
- [ ] Intermediate opens more modelling / rendering / import controls.
- [ ] Advanced shows Rig Check and the OptiBlend Advanced sidebar.
- [ ] Switch Beginner -> Intermediate -> Advanced -> Beginner several times.

## Advanced retopology
- [ ] Duplicate a test mesh first.
- [ ] Run QuadriFlow with a target face count.
- [ ] Run Triangulate as a non-destructive modifier.
- [ ] Run Subdivision-Ready setup.

## Mixamo / rig readiness
- [ ] Select a character mesh and run Mixamo Readiness.
- [ ] Confirm score is labelled heuristic.
- [ ] Confirm transform / centering results make sense.
- [ ] Confirm quads/tris/ngons are reported.
- [ ] Confirm loose / non-manifold / island checks appear.
- [ ] Confirm armature state is reported.
- [ ] Confirm modifiers are reported.
- [ ] Confirm particle systems / particle modifiers / Geometry Nodes are reported.
- [ ] Confirm unrelated visible scene objects create a warning.
- [ ] Confirm manual humanoid / neutral-pose checks are shown rather than automatically passed.

## Advanced pipeline
- [ ] Performance Audit.
- [ ] FBX / Export Prep.
- [ ] Team Collection Blocks.
- [ ] UV Helper.
- [ ] Weighted Normals Fix.
- [ ] Modifier Stack Helper.

## Final package
- [ ] README.md included.
- [ ] HCI_REPORT.md included.
- [ ] MIXAMO_RESEARCH.md included.
- [ ] LICENSES.txt included.
- [ ] COPYING included.
- [ ] No Python syntax errors on enable.


## Final Beginner Outliner Behaviour
- Enter Beginner mode and confirm the former Properties-side area is now the Outliner.
- Confirm the other original Outliner becomes the UV/Image Editor helper.
- Re-apply Beginner mode twice and confirm the editors do not swap incorrectly.
- Switch Beginner -> Intermediate -> Advanced and confirm the original Properties + Outliner editors restore.


## GitHub / release package
- [ ] `bl_info` shows OptiBlend version 1.0.0.
- [ ] ZIP installs without manually extracting it.
- [ ] README.md renders correctly on GitHub.
- [ ] LICENSE and LICENSES.txt are included.
- [ ] No `__pycache__`, `.pyc` or temporary Blender backup files are included.
- [ ] Q Helper, L Test Lab and all three modes still work after the release wording cleanup.
