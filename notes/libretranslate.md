# Optional Japanese-to-English quest translation

This draft adds LibreTranslate to Quest Strings. Manual editing and offline
Objective/Success/Failure templates remain available without any service.
LibreTranslate is a machine translator, not a generative summarizer. The editor
wraps text and blocks estimated overflow; it never truncates descriptions.

## Start a service

Use an existing LibreTranslate instance, or install one on your own machine.
The instance needs a Japanese-to-English Argos model. The official supported
language list includes this direction; an individual deployment may not have
installed it. Self-hosted software is free; third-party hosting may be paid.

With Docker already installed and running, this local-only example loads the
two relevant languages (the first startup downloads models):

```sh
docker run --rm -p 127.0.0.1:5000:5000 libretranslate/libretranslate --load-only ja,en
```

Keep that terminal running. The editor's default base URL is
`http://localhost:5000`. No key is required unless your instance requires one.
The editor does not install Docker, download models, or contact a public mirror
automatically. A shared server needs a valid HTTPS endpoint; remote plain HTTP
is deliberately refused. API keys are kept in component memory, not saved to
quest files, exports or browser storage.

Official setup and language references:

- https://docs.libretranslate.com/guides/installation/
- https://docs.libretranslate.com/guides/supported_languages/
- https://docs.libretranslate.com/api/operations/translate/

## Translate one quest

1. Open the quest in the editor and visit Quest Strings.
2. Enable LibreTranslate. Configure its base URL and optional key.
3. Select fields. Title, quest giver and description are selected initially;
   Objective/Success/Failure can instead use offline templates.
4. Keep "only fields containing Japanese" enabled to preserve existing English.
5. Generate a preview. Review the original and edit the translation if needed.
6. Shorten any overflowing text manually, then apply it to the form.
7. Use the existing save flow only after review. The single-quest tab still uses
   the existing quest parser/save implementation, not the batch text-only writer.
   Keep a backup; custom BIN parser hardening is separate work.

The column limit starts at 28 and is adjustable. It estimates character count,
not exact game-font pixel width. Description line limits come from the source
line count. Other default budgets are title 2, objectives/giver 1, conditions 2.
Native validation rejects unsupported Shift-JIS characters and NUL/control data.

## Translate multiple variants

Select 1–500 BIN files from the batch section. Names must be five-digit IDs plus
d0/d1/d2/n0/n1/n2 (optional underscore). Embedded IDs must match the filename.
Each file is inspected independently; missing variants are reported, not created.
All eight strings are read, while only selected fields are sent for translation.
Identical source text on the same provider reuses session memory. No files are
written until the user chooses Export.

Review editable per-file previews, then choose a separate output directory.
Originals remain unchanged, existing output names are refused, and changed
sources are rejected until inspected again. Only the master text-table pointer
and an appended string table/text region are changed in the decoded payload.
The output is decoded again and compared with that intended payload.

Supported layers: raw quest, ECD, JPK0/JPK3 and JPK4 decoding. JPK4 needs the
explicit JPK3 conversion checkbox because its original compression is not encoded
by this implementation. JPK3 encoding uses literals, so files can become larger.
The report identifies conversion. JPK2 and unsupported/custom layouts are
rejected; this feature does not universally repair malformed community quests.

The report remains visible in the batch panel. The output is not deployed or
uploaded automatically. Test a sample in the actual client before replacement.

## Two separate size limits

Line/width estimates protect the visible UI. A second check protects Erupe's
event enumeration packet: for v9.6.1 ZZ with its normal empty debug string,
frame length is 384 plus the combined Shift-JIS byte lengths of the eight fields.
The server limit is 896, leaving **512 encoded text bytes**. Apply/export blocks
larger text. Other client modes or nonempty debug strings require a separate
profile; this is not a universal limit for every Frontier build.

Source: https://github.com/Houmgaor/Erupe/blob/v9.6.1/server/channelserver/handlers_quest.go

## Development checks and limitations

```sh
node --experimental-strip-types --experimental-test-coverage --test tests/*.test.mjs
cargo test --manifest-path native-tests/Cargo.toml
yarn lint
yarn check-types
```

The standalone native test harness imports the production modules but excludes
desktop command attributes through its `portable-tests` feature. It tests URL,
encoding, packet budget, pointers, text-only preservation and synthetic codec
fixtures without pulling in WebKit/GTK. The normal desktop build still registers
all commands. Do not enable `portable-tests` when building the actual desktop app.

No live LibreTranslate service or real-file in-game round trip has been tested
in this development environment. Quality, terminology and exact font fit need
review. Existing Linux CI has a Wry/WebKit dependency build failure predating
these changes; the portable test job isolates the new native code from it.

The TypeScript suite includes 56 tests, including preservation of manual line
breaks; 13 native Rust tests passed in CI. Frontend lint and type
checks also passed. Rust formatting is checked separately in the portable job.

ECC research-first, test-first verification and independent native-code review
were used. No credentials or global ECC configuration were installed.
