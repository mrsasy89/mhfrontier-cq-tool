# Portable Quest Builder rules

These are domain and workflow rules, not private model instructions. Version changes and link them to evidence. Keep secrets and personal logs out of the knowledge package.

Research leads supplied by the user are maintained in [SOURCES.md](SOURCES.md) and [sources.json](sources.json). Verify relevant files/revisions before use; the registry is not a claim that every source was audited.

1. Read the current file and record its hash first: an old status document, title or ID does not identify the actual revision.
2. Distinguish user requests, verified BIN facts, corpus correlations, hypotheses, client tests and unidentified parameters.
3. Preserve the initial revision, diff and rationale for every correction. Keep experimental and final versions distinct.
4. Research before editing: the exact requested base, species, rank, map and phase, area/stage, season/time, variants and dependent fields.
5. A map is a data package: equal IDs do not imply equal zones, zone order, transitions, minions, entrances or resources. Record the complete base's provenance.
6. Prefer spawn references using the same species and stage. Another species' spawn supports terrain placement, not AI or migration compatibility. Do not invent XYZ coordinates. Pixel and world coordinates need independent calibration for each area and variant.
7. UI labels are not a client specification. An example requiring audit is MaxDeaths exposed as a byte versus the u32 CartsOrRewardReduction field in references. Do not extend incomplete interpretations by analogy.
8. Validate reward headers, lists, terminators, IDs, quantities and weights. A total of 100 alone does not prove client reward delivery. A weight is not a quest-wide probability.
9. Damage uses a damage threshold with the verified scale of 100 points per unit. For percentage objectives, show reference HP, requested threshold, rounding and effective percentage. Do not set monster HP through objective quantity.
10. Main, SubA, SubB and requirement_to_finish must agree with text and rewards. Do not introduce duplicates or SlayAll automatically; preserve a working case before adding requirements.
11. Species, class/stat table, variant selector and HC/G flags are distinct interacting fields. 10 does not automatically mean HC; 9 does not create a Supremacy form for an arbitrary species; 16 is not a Zenith level.
12. Repel threshold completion, retreat animation, disappearance and hunter return are distinct events. Do not infer a 20-minute timer or instant return from labels.
13. Absence from the corpus does not prove impossibility. Allow clearly marked experimental proposals with limitations and required tests, without presenting them as verified.
14. A preview represents data; it does not emulate AI, loading or combat. Do not call it an in-game simulation without an actual simulator.
15. Keep the corpus read-only by default and work in a separate folder. Export, installation and server registration are distinct operations. Respect persistent user authorization without unnecessary repeated questions.
16. Produce d0/n0 and other required variants according to the verified loader/profile. The d0 filename alone does not set daytime. Enabled BinCustom does not prove the active process reads it.
17. An ID unused in files may still be occupied in the database. Do not implicitly execute SQL, restart processes or overwrite unrelated files during generation.
18. SQL and event files depend on the server profile: do not treat every 9.3+ installation as identical. Preserve the exact query and, for database changes, the relevant previous state without credentials in reports.
19. EOF is an observed disconnection, not a crash diagnosis. Correlate player, quest, time and revision where possible. Do not invent error meanings for UNK fields.
20. Record granular outcomes: loading, spawn, combat, area changes, completion and rewards. Success in one does not certify the others. Later corrections do not erase previous failures.
21. Use targeted content-based backups with hashes and shared caches. Avoid copying large archives, toolchains or dependencies for each test. Never automatically delete unique data.
22. Separate general product rules from laboratory-specific paths, Git history and checkout conventions.
23. Search all quests in the configured source, whether a server directory or an internal project folder. Laboratory cases are regression evidence, not a closed list of references.
24. Inventory unreadable and unsupported files and report actual coverage. Do not claim full corpus analysis while some files remain undecoded.
25. Preserve every file variant and its role, even when hashes are identical. Physical deduplication must not remove a variant required by the loader.
26. Keep the corpus, generated output, backups and user projects separate. Generated quests may become references only through explicit promotion with provenance; do not automatically label them original or verified in game.
27. Quest Fix must read CartsOrRewardReduction as u32. HR reward-penalty and G direct-cart profiles require separate evidence. A byte-only write can corrupt an existing penalty. Conditional arithmetic is not traced client behavior; preserve an existing penalty that already reaches the requested faint count. Do not apply one correction across every quest.
28. Preserve intentional Diva/Interception flags for sequential spawns. Four hunter slots do not establish NPC eligibility; inherited unknown fields are candidates for comparison, not bytes to zero blindly. A native-base rebuild must preserve requested custom content and validate transferred pointer graphs; gameplay outcomes remain pending until reported.
29. Reward reports for designers should prioritize mission names, monsters, Main/Sub item names, quantities and configured table weights, with category filtering when requested. Report totals other than 100 without normalizing or claiming quest-wide probabilities.
