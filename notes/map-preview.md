# Map preview correction

Snowy Mountains Day/Night used plural display names to construct image paths, while the existing asset directories are Snowy Mountain Day/Night. Resolve the asset directory explicitly without changing map IDs, area IDs, or quest binaries. The same resolver covers the existing Castle Schrade and Tower naming differences.

The user-supplied overview is a reference for Snowy Mountain. This change reuses the existing per-area PNGs; it does not substitute the full overview for an area image or invent coordinate calibration.

The preview adapts to narrow panels. Pointer coordinates are scaled to the actual canvas dimensions. Image handlers are registered before loading and cancelled when the selected area changes.

For uncalibrated areas (including Snowy Mountain), show the area image with a preview-only notice. Do not render world coordinates as pixels or write clicked pixels into quest coordinates. Manual X/Y/Z fields remain available. The developer calibration screen can still explicitly use pixel mode.

Validation: `node tests/mapPreview.test.mjs`. CI additionally checks the actual Snowy Mountain files, lint, TypeScript and the Vite production bundle. Windows/Tauri visual inspection and in-game spawn verification remain manual checks; no binary modifications are part of this fix.
