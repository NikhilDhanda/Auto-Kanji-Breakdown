# Cleanup and removal

To remove Auto Kanji Breakdown's displays or generated information, open
**Tools > Auto Kanji Breakdown > Cleanup...**. Select a note type and a mode,
review the proposed changes, then apply only the changes you want.

| Mode | What it removes | What it keeps |
| --- | --- | --- |
| Remove visual breakdown only | The add-on's display on the cards | Breakdown data and automatic generation |
| Clear breakdown data | Recognizable generated breakdown data; automatic generation is turned off | Card displays and fields |
| Full cleanup | The add-on's display and recognizable generated data; automatic generation is turned off | Japanese source fields and unrelated content |

Japanese source fields, notes, cards, scheduling and review history are not deleted.
Collection cleanup is undoable through Anki. The result tells you what actually
changed, including cleared notes and fields deleted or kept.

## Optional field deletion

Full cleanup can also delete fields proven to have been created by Auto Kanji
Breakdown. It is off by default. User-created fields are kept. A name alone is
not enough to prove a field belongs to the add-on.

If a field contains unsupported content, is still referenced elsewhere on your
cards, or cannot be safely identified, deletion is refused. Do not assume the
rest of that cleanup completed: read the warning, leave deletion off and preview
again. Suspicious content is preserved when clearing generated data.

## Optional downloaded-data removal

Full cleanup can remove the add-on's downloaded kanji databases and local update
state, and turn automatic data checks off. This affects all note types using that
add-on installation. Unrelated files are kept. **This file removal is not undoable.**

## Uninstalling

Run cleanup for the configured note types first if you want their displays/data
removed. Then remove the add-on through Anki's Add-ons window. Uninstalling the
Python add-on alone leaves existing synced breakdowns on your cards. Do not rely
on downloaded databases surviving uninstall; a reinstall includes the bundled data.

[Configuration safeguards](development/configuration.md) · [FAQ](faq.md)
