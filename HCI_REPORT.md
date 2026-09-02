# OptiBlend Final V1 - HCI Report

## Main HCI direction

OptiBlend Final V1 keeps the project focused on progressive disclosure. Beginner users are shown the smallest useful workflow first, Intermediate users get more freedom, and Advanced users get the full modelling / pipeline feature set.

The main HCI ideas used are visibility of system status, recognition rather than recall, consistency, user control, error prevention, progressive disclosure, contextual help and reducing unnecessary interface complexity.

## Dan Turnbull feedback

Dan said snapping was unfamiliar and wanted it to be very obvious that Q starts OptiBlend. He also wanted the tutorial concept replaced with an OptiBlend Guide and wanted Q to close the Helper as well.

Implemented:
- `PRESS Q = HELPER` is visible for Beginner / Intermediate.
- Q opens and closes the same Helper.
- Guide teaches actual Blender commands rather than a separate OptiBlend control language.
- Beginner uses Grid placement and the Move tool automatically.
- Edit Mode Smart Snap uses vertex / edge / face / midpoint targets where supported.

## Maksim Petrovic feedback

No specific written change was attached to Maksim's name in this feedback set, so the release does not invent a requirement for him. This keeps the stakeholder evidence accurate.

## Matthew Hermite feedback

Matthew wanted tools to be easier to understand, drag placement to be much easier to see, advanced retopology, and a bigger close target.

Implemented:
- custom hover mini-tools are drawn inside the Q Helper rather than switching to normal Blender dropdowns
- contextual hover descriptions
- glowing drag outline and green preview
- larger asset-bar close X
- QuadriFlow quad retopology
- Triangulate modifier option
- Subdivision-Ready setup
- centred XYZ helper around visible geometry rather than an offset object origin

## Advanced rig / Mixamo feedback

A new Advanced-only Rig Check was added. It is intentionally hidden from Beginner and Intermediate because it introduces pipeline concepts that a new Blender user does not need yet.

The Advanced character workflow now includes:
- Mixamo Readiness Check
- Topology Audit
- Rig / Modifier / Particle Audit
- Retopology actions
- FBX / export preparation
- research notes explaining which Mixamo conditions came from Adobe documentation

The Mixamo score is labelled a heuristic. This is an HCI decision as well as a technical one: it is better to show a clear manual check than to give a misleading automatic PASS for things such as humanoid anatomy or neutral pose.

## Jia feedback

Jia requested the ability to import external objects directly through OptiBlend.

Implemented:
- Import option in OptiBlend
- FBX, OBJ, GLTF/GLB and STL support where the corresponding Blender importer is available
- imported objects remain selected
- Move tool is enabled after import
- optional Auto Collections organisation
- optional import scan reporting object / polygon information

## Hover interaction

Normal Blender operators can use `bl_description` for tooltips. The Q Helper is custom GPU-drawn UI, so its parent and child cards use manual hit testing and OptiBlend-drawn descriptions.

This means the detailed controls only appear when their parent is hovered. It reduces the amount of information permanently visible and supports progressive disclosure.

## Beginner / Intermediate / Advanced depth

### Beginner
- smallest workspace set
- shapes/materials/guide first
- clear Q instruction
- Grid snapping
- Move tool enabled
- centred XYZ helper
- advanced pipeline hidden

### Intermediate
- Blender opens up more for confident users
- more workspaces and normal modelling tools
- modifiers / render / import / scene tools available
- hover help still active
- advanced rig pipeline remains hidden

### Advanced
- almost full Blender workspace access
- full OptiBlend menu depth
- Advanced OptiBlend sidebar
- retopology
- Mixamo / rig checks
- topology audits
- particle / modifier checks
- pipeline / FBX preparation
- performance and collaboration helpers

## Colour / visual language

Final scheme: **OptiMint**
- Mint/green = action / positive status
- Cyan = beginner help / snapping / guide
- Purple = materials and Advanced depth
- Orange = render / warning emphasis
- Dark charcoal = background

Different modes use different base accents so the user can tell that they have moved into a different level of complexity.

## HCI conclusion

The aim is not to hide Blender forever. The aim is to reduce the initial learning barrier, teach actual Blender fundamentals, and then progressively return control and complexity as the user becomes more confident.

## References

Nielsen Norman Group - Ten Usability Heuristics:
https://www.nngroup.com/articles/ten-usability-heuristics/

Blender Python API:
https://docs.blender.org/api/current/

Adobe Mixamo FAQ:
https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html

Adobe Mixamo upload / rigging guide:
https://helpx.adobe.com/creative-cloud/help/mixamo-rigging-animation.html
