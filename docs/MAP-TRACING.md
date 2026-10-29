# Cross-source map overview tracing

The packaged `mhfz_builder/data/map_tracing.json` preserves explicit visual associations, evidence and review states. It is not a binary client texture-selector table. Entries apply only when the configured native PNG's SHA256 matches the researched revision. Local user bindings override packaged defaults for the same map ID.

## Review states

- **user_confirmed**: directly identified by the user; this does not imply a gameplay or coordinate-calibration test.
- **cross_checked_visual**: compared with Frontier visual sources and local asset/quest information.
- **variant_pending**: the location family is recognized, but Day/Night, floor numbering or exact variant still needs review.
- **candidate_review**: a proposed association awaiting user confirmation; source links may provide context rather than confirm the texture number.
- **partial_overview**: only a section of the map is represented; additional views are required.

Map association review is conducted in chat with the project maintainer. The application has no R review command, --review option, review filter or unassigned texture research grid. Internal evidence/states are preserved for research and show only brief provisional/partial-preview notices where needed. Use V for ordinary previews. L shows all catalog map names in the terminal; N/P browses shorter pages. Existing historical HTML reports remain preserved but are not the current application workflow.

## Evidence and corrections

The user-supplied gallery is regression evidence, not an independent authority confirming its own labels. The older extraction's visual labels are preserved unchanged and overridden in the application only for the matching PNG revision.

Cross-checking native textures with [Ferias' Frontier gathering overview index](https://xl3lackout.github.io/MHFZ-Ferias-English-Project/saisyu/sugo.htm), its linked maps and local quest/catalog data identified these corrections:

- texture43: Tidal Island surface, not Flower Field; underground views remain necessary;
- texture44: Flower Field, not White Lake;
- textures49/50: White Lake Day/Night, not Painted Waterfalls; area6 differs;
- texture41: World's End, explicitly confirmed by the user against an identical RGBA image.

The World’s End preview hides the icon footer with a display viewport. The original 256x256 PNG stays unchanged and is linked separately. Display cropping is not geometry generation or world-coordinate calibration.

The Ferias reference revision inspected was `b7911a0f8c87891f7196ef8c394e182f062e9d57`. Reference image downloads were checked against their Git blob hashes and kept in the private laboratory, not distributed. [The Tower page](https://xl3lackout.github.io/MHFZ-Ferias-English-Project/saisyu/tou-sugo.htm) explicitly warns that area4/5 numbering varies. The local Town Night catalog is also incomplete: parsed quests use stage182 even though that catalog entry lists only Base. Treat neither catalog labels nor source screenshots as a complete transition graph.

The user additionally supplied [Fandom Locations](https://monsterhunter.fandom.com/wiki/Category:Locations). Use only Frontier-specific material, checking MHF/MHF-Z/MHF-ZZ appearances and image versions. [Frontier Exclusive Areas](https://monsterhunter.fandom.com/wiki/Category:Frontier_Exclusive_Areas) helps discovery. Mixed-game pages and Freedom Unite references must not silently define Frontier numbering, layouts, variants or coordinates.

## Current scope

59 of the 85 catalog IDs have a proposed or identified overview association. This includes partial references and candidates, **not 59 confirmed complete maps**. Siege and World's End have direct user confirmation. The remaining entries include arenas, Sky Corridor variants, Raviente depth phases, Caravan Balloon and Hunter's Road. Some are dynamic/multi-view cases; no one-image association is fabricated for them. Final user review and additional source checks remain required.
