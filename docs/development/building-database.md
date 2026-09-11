# Building the database

The shared deterministic builder uses Python 3.9+ and the standard library. To
build the add-on itself, the included generated database is enough; this page is
for developers reproducing or deliberately refreshing that database.

Acquire authoritative source archives separately and leave their bytes unchanged
in ignored data_sources/: kanjidic2.xml.gz and kanjivg-20250816-main.zip.
See [the official-source links and exact hashes](../ATTRIBUTION.md). EDRDG's live file
changes over time; exact historical reproduction requires preserved original bytes.
Do not commit the archives or silently replace approved snapshots with newer data.

```sh
python tools/build_database.py
python -m tools.audit_components
```

The builder validates and writes generated/kanji_db.json, generated/build-stats.json
and the matching manifest sidecar. --kanjidic, --kanjivg, --output and --stats let
you stage separate candidate outputs. Each development output replacement is atomic,
not a transaction across all outputs. Review hashes, statistics, licences and tests
before adopting an update; never manually patch generated records.

[Database schema](database-schema.md) · [Component audit](unresolved-components.md)
· [Release process](releasing.md) · [Installed update architecture](database-update-architecture.md)
