# Developer documentation

Read [contributor principles](principles.md) before changing data or collection behavior.

## Build and test

- [Build and release](releasing.md): package allowlists, dependencies and reproducibility.
- [Testing](testing.md): compatibility guards and repeatable desktop/mobile checks.
- [Build the database](building-database.md): source inputs, validation and regeneration.

## Architecture and contracts

- [Runtime](runtime-architecture.md) and [Anki API boundaries](anki-api.md).
- [Configuration and ownership](configuration.md) and [manual regeneration](manual-regeneration.md).
- [Renderer](renderer-architecture.md) and [structural rendering policy](rendering-policy.md).
- [Database schema](database-schema.md), [payload schema](payload-schema.md) and [updater](database-update-architecture.md).
- [Unresolved components](unresolved-components.md): source limitations and normalization evidence.

Keep dated verification results in local release records. Maintained documentation
should describe current contracts and repeatable procedures, not implementation diaries.

[Documentation assets](assets.md): image provenance and contributor capture instructions.
