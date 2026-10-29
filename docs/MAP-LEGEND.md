# Map legend and local image gallery

## Complete maps and multiple overviews

Area crops are supplementary details and are never used as the main map preview. The primary preview uses an explicit full-overview binding, and displays **every** overview/layer assigned to that map ID. Tower1, Tower2, Tower3 and other variants remain distinct. Binding metadata carries a label, SHA256 and evidence status for each image. No automatic first-image choice or family-name merge is performed.

The optional local `map_overview_index` configuration points to a JSON object keyed by quest map ID; each value is a list of `{path, sha256, label, status}` records. This supports one map with several overview images. `native_map_index` may point to the original extraction index of `map.txb`. The native collection remains available to the research engine, including wide/multi-part atlases and unassigned resources. The application gallery displays associated previews only; unassigned texture review is conducted in chat. Texture indices are never interpreted as quest map IDs. Missing map-to-overview bindings remain explicit instead of falling back to an area crop.

The user-designated complete Siege Fortress Day PNG is an explicit visual reference for map1. Other associations require individual review; the existence of 85 catalog entries and 59 native textures does not establish a complete one-to-one mapping. Some native textures are atlases or UI-related resources, and variants can share or require several images.

[GameFAQs' Freedom Unite map guide](https://gamefaqs.gamespot.com/psp/943356-monster-hunter-freedom-unite/faqs/78652/tower) is a secondary visual comparison source. It concerns **Monster Hunter Freedom Unite**, not Frontier. Similarity does not establish equal layouts, numbering, transitions, rank variants or collision/spawn coordinates. Frontier's extracted assets and quest data take precedence; cross-game differences must remain visible and FU images must not be silently substituted as Frontier assets.

The map-selection prompt now starts with a paginated legend: exact catalog ID/name, parsed quest-file reference count and local preview availability. `N` and `P` change page; `L` displays the complete map-name legend, including entries beyond the current page. Enter an ID or part of a name to choose. Blank still lets the quest prompt decide; `B` returns to the previous step.

Enter `V` to generate/open a local gallery, or `V 15` to scroll to map15. The browser has a search field, minimap thumbnails and expandable local assets. Return to the terminal and enter the map ID to select it; viewing images does not select or modify a quest.

Images are reused from an existing folder, never copied, bundled or uploaded. Configure it under **Settings > Local map preview images**. Expected layout is one directory per map name containing PNG files. A small explicit folder-name alias list handles Tower01/02/03, Schrade Castle and Snowy Mountain naming differences. Other missing matches remain explicit rather than guessed. The optional image directory is local configuration and is not published.

CLI alternatives:

```powershell
python -m mhfz_builder maps
python -m mhfz_builder maps --gallery --open
python -m mhfz_builder maps --gallery --images "C:/My existing map images"
```

The HTML is stored under workspace/map-gallery and refers to local image files through file URLs. It has no remote image/font/script dependencies. Without local images the complete catalog and reference counts remain usable, and missing previews are labelled clearly.

This is a visual reference, not a client simulator or calibrated spawn editor. Image filenames are shown as asset names, not certified area numbers. Images and broad folder aliases do not prove stage transitions, native quest-package compatibility or spawn coordinates. Pixel-to-world mapping requires independent calibration and gameplay verification. Day/Night and different native packages must not be merged merely because they share a name or silhouette.
