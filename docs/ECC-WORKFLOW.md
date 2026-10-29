# ECC development workflow

ECC is used as verified development guidance, not as a quest-format authority. Reviewed revision: 25278e7d7b6cf6e6a4e7a6c8e10f14ff22f0eb5b.

Apply search-first in inline mode: search this repository, the existing CQ editor and available tools before adding dependencies or duplicate workflows. Preserve the independent builder and reuse existing toolchains. No global agent settings or hooks are installed automatically.

Apply verification-loop: build, type checking, scoped lint where configured, meaningful regression tests, secret/data review and final diff review. Record failed and skipped checks honestly; missing coverage tools do not establish a coverage percentage. Client gameplay is a separate user-run check.

References:

- https://github.com/affaan-m/ECC/blob/25278e7d7b6cf6e6a4e7a6c8e10f14ff22f0eb5b/skills/search-first/SKILL.md
- https://github.com/affaan-m/ECC/blob/25278e7d7b6cf6e6a4e7a6c8e10f14ff22f0eb5b/skills/verification-loop/SKILL.md
