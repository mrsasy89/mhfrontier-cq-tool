# References and attribution

An AI integration branch of MHFrontier CQ Tool maintained by mrsasy89, distributed under LICENSE (LGPL v3). The monster and map name/ID catalog derives from data in mhfrontier-cq-tool: https://github.com/mrsasy89/mhfrontier-cq-tool. The parser and adapter are new implementations based on the studied format and comparison with that project.

ReFrontier remains an external program under its own licenses. No ReFrontier executable, source code or game assets are included.

The primary `src/` interface and `src-tauri/` native editor derive from MHFrontier CQ Tool / MHFrontier Dev Tools (https://github.com/Invasor-de-Fronteiras/mhfrontier-cq-tool and https://github.com/mrsasy89/mhfrontier-cq-tool), including its better_cursor library and metadata catalogs. The imported local source was based on commit 1176c07ede6770117684f2643efd3315a940872b, with existing local changes. Their LGPL v3 license is preserved in desktop/LICENSE. Original contributors retain their copyrights. Modifications add the AI tool, Python wizard bridge, workspace-only backed-up quest saves, a u32 failure field, and disable direct ReFrontier/remote database actions in this beta. No original game BINs or client map textures are included.
