# OptiBlend Final V1 - Mixamo Research Notes

Research checked for the Advanced Rig / Mixamo Readiness feature.

## Adobe Mixamo requirements used

Adobe's Mixamo guidance says the current automatic rigging system is for **bipedal humanoid characters**. It advises that the character should have clearly distinguishable head/body/arm/leg areas, should be in a neutral/default pose, should avoid large extra appendages or props, should not include unrelated content, should not have gaps between body parts, should be centred at the world origin, and should use a clean/error-free mesh.

Adobe also documents custom-character uploads as **FBX, OBJ or ZIP**. For a character that is already rigged, Adobe documents the upload as **FBX**.

Sources:
- https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html
- https://helpx.adobe.com/creative-cloud/help/mixamo-rigging-animation.html

## What OptiBlend can actually test

OptiBlend can test mechanical Blender data such as:
- active object is a mesh
- object centre relative to world origin
- applied scale / rotation
- triangle / quad / ngon counts
- non-manifold / boundary edges
- loose geometry
- disconnected mesh islands
- armature presence
- modifier stack
- legacy particle systems / particle modifiers
- Geometry Nodes modifiers
- unrelated visible scene objects

## What OptiBlend cannot reliably prove

The add-on cannot truthfully guarantee these from geometry data alone:
- whether the character looks humanoid enough for Mixamo
- whether proportions are suitable
- whether the pose is truly neutral
- whether clothing / hair / props will confuse the auto-rigger
- whether every animation will deform correctly

For that reason OptiBlend calls the result a **heuristic readiness score**, and the report includes manual checks instead of giving false PASS results.
