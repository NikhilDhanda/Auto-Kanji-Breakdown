"""Offline, deterministic KANJIDIC2/KanjiVG database build (standard library only)."""

import copy
import gzip
import hashlib
import json
from pathlib import Path
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter

KVG = "{http://kanjivg.tagaini.net}"
G = "{http://www.w3.org/2000/svg}g"
ATTRIBUTES = {
    "element": "char", "original": "base", "position": "position",
    "radical": "radical", "phon": "phon", "variant": "variant",
    "partial": "partial", "part": "part", "number": "number",
    "tradForm": "tradForm", "radicalForm": "radicalForm",
}
FLAGS = {"variant", "partial", "tradForm", "radicalForm"}
MAX_XML = 128 * 1024 * 1024
MAX_ZIP_ENTRIES = 30000
MAX_ZIP_TOTAL = 256 * 1024 * 1024
MAX_SVG = 2 * 1024 * 1024


def xml_root(xml):
    if len(xml) > MAX_XML or b'\x00' in xml or b'<!ENTITY' in xml.upper():
        raise ValueError('XML size/entity limit')
    root = ET.fromstring(xml)
    pending = [(root, 0)]
    count = 0
    while pending:
        node, depth = pending.pop()
        count += 1
        if depth > 80 or count > 2000000:
            raise ValueError('XML structure limit')
        pending.extend((child, depth + 1) for child in node)
    return root


def parse_kanjidic(xml: bytes) -> tuple[dict, dict, dict]:
    root = xml_root(xml)
    if root.tag != "kanjidic2" or root.find("header") is None:
        raise ValueError("Expected KANJIDIC2 with a version header")
    metadata = {e.tag: e.text for e in root.find("header")}
    if (set(metadata) - {'file_version', 'database_version', 'date_of_creation'}
            or not all(isinstance(value, str) and value for value in metadata.values())):
        raise ValueError('Unsupported KANJIDIC2 header')
    entries = {}
    stats = Counter()
    for character in root.findall("character"):
        char = character.findtext("literal")
        if not char or len(char) != 1 or char in entries:
            raise ValueError(f"Invalid or duplicate KANJIDIC2 literal: {char!r}")
        record = {"meanings": [], "readings": {"on": [], "kun": []}}
        strokes = character.findall("misc/stroke_count")
        if strokes:
            record["strokes"] = int(strokes[0].text)
        stats["alternative_stroke_counts"] += max(0, len(strokes) - 1)
        freq = character.findtext("misc/freq")
        if freq is not None:
            record["frequency"] = int(freq)
        groups = character.findall("reading_meaning/rmgroup")
        stats["multiple_reading_meaning_groups"] += int(len(groups) > 1)
        for group in groups:
            record["meanings"].extend(m.text for m in group.findall("meaning")
                                      if m.get("m_lang", "en") == "en")
            for reading in group.findall("reading"):
                kind = {"ja_on": "on", "ja_kun": "kun"}.get(reading.get("r_type"))
                if kind:
                    record["readings"][kind].append(reading.text)
        entries[char] = record
    if not entries:
        raise ValueError("KANJIDIC2 has no characters")
    return entries, metadata, dict(stats)


def parse_svg(xml: bytes, char: str) -> dict:
    svg = xml_root(xml)
    containers = [g for g in svg.iter(G)
                  if g.get("id", "").startswith("kvg:StrokePaths_")]
    if len(containers) != 1:
        raise ValueError(f"{char}: expected one stroke-path container")
    roots = containers[0].findall(G)
    if len(roots) != 1 or roots[0].get(KVG + "element") != char:
        raise ValueError(f"{char}: missing or mismatched structural root")

    def node(group):
        result = {}
        for name, value in group.attrib.items():
            if not name.startswith(KVG):
                continue
            key = name[len(KVG):]
            if key not in ATTRIBUTES:
                raise ValueError(f"{char}: unsupported KanjiVG attribute {key}")
            if key in FLAGS:
                if value not in {"true", "false"}:
                    raise ValueError(f"{char}: invalid flag {key}={value}")
                value = value == "true"
            result[ATTRIBUTES[key]] = value
        # Keep unnamed groups and split parts: promoting children changes meaning.
        children = [node(child) for child in group.findall(G)]
        if children:
            result["children"] = children
        return result

    return node(roots[0])


def parse_kanjivg(path: Path) -> tuple[dict, dict]:
    structures = {}
    skipped = []
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_ZIP_ENTRIES or sum(i.file_size for i in infos) > MAX_ZIP_TOTAL:
            raise ValueError('ZIP size/count limit')
        if len({i.filename for i in infos}) != len(infos):
            raise ValueError('Duplicate ZIP member')
        for info in infos:
            name = info.filename
            if (name.startswith('/') or '\\' in name or ':' in name or '..' in name.split('/')
                    or info.file_size > MAX_SVG or (info.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError('Unsafe ZIP member')
        names = sorted(n for n in archive.namelist() if n.endswith(".svg"))
        for name in names:
            match = re.fullmatch(r"([0-9a-fA-F]{5,6})\.svg", Path(name).name)
            if not match:
                skipped.append(name)
                continue
            char = chr(int(match[1], 16))
            if char in structures:
                raise ValueError(f"Duplicate canonical KanjiVG glyph: {char}")
            structures[char] = parse_svg(archive.read(name), char)
    if not structures:
        raise ValueError("KanjiVG has no canonical glyphs")
    return structures, {"kanjivg_glyphs_inspected": len(names),
                        "noncanonical_glyphs_skipped": skipped}


def walk(node):
    yield node
    for child in node.get("children", []):
        yield from walk(child)


def component_meanings(node: dict, entries: dict) -> list[str]:
    """Resolve only the local explicit original, otherwise the displayed element."""
    return entries.get(node.get("base", node.get("char")), {}).get("meanings", [])


def merge(entries: dict, structures: dict) -> dict:
    result = copy.deepcopy(entries)
    for char in result.keys() & structures.keys():
        result[char]["structure"] = copy.deepcopy(structures[char])
    return result


def validate(database: dict) -> None:
    def require(condition, message):
        if not condition:
            raise ValueError(message)

    def strings(value):
        return isinstance(value, list) and all(isinstance(v, str) and v for v in value)

    require(set(database) == {"schema_version", "generated", "sources", "entries"}, "Invalid envelope")
    require(type(database["schema_version"]) is int and database["schema_version"] == 1,
            "Unsupported schema version")
    require(database["generated"] is True, "Missing generated marker")
    require(isinstance(database["sources"], dict) and
            set(database["sources"]) == {"kanjidic2", "kanjivg"}, "Invalid sources")
    for source in database["sources"].values():
        require(isinstance(source, dict) and isinstance(source.get("file"), str) and
                re.fullmatch(r"[0-9a-f]{64}", source.get("sha256", "")) is not None,
                "Invalid source identity")
    require(isinstance(database["entries"], dict) and bool(database["entries"]), "Empty entries")
    for char, entry in database["entries"].items():
        require(isinstance(char, str) and len(char) == 1 and not 0xD800 <= ord(char) <= 0xDFFF,
                "Invalid character")
        require(isinstance(entry, dict) and {"meanings", "readings"} <= entry.keys() and
                entry.keys() <= {"meanings", "readings", "strokes", "frequency", "structure"},
                f"{char}: invalid record fields")
        require(strings(entry["meanings"]), f"{char}: invalid meanings")
        require(isinstance(entry["readings"], dict) and set(entry["readings"]) == {"on", "kun"},
                f"{char}: invalid readings")
        require(all(strings(v) for v in entry["readings"].values()), f"{char}: invalid readings")
        for key in ("strokes", "frequency"):
            if key in entry:
                require(type(entry[key]) is int and entry[key] > 0, f"{char}: invalid {key}")
        if "structure" not in entry:
            continue
        require(isinstance(entry["structure"], dict) and entry["structure"].get("char") == char,
                f"{char}: invalid structure root")

        def check_node(node):
            require(isinstance(node, dict), f"{char}: invalid node")
            require(node.keys() <= set(ATTRIBUTES.values()) | {"children"}, f"{char}: unknown node fields")
            for key, value in node.items():
                if key == "children":
                    require(isinstance(value, list) and bool(value), f"{char}: invalid children")
                    for child in value:
                        check_node(child)
                elif key in FLAGS:
                    require(type(value) is bool, f"{char}: invalid flag")
                else:
                    require(isinstance(value, str) and bool(value), f"{char}: invalid annotation")
        check_node(entry["structure"])


def encode(database: dict) -> bytes:
    return (json.dumps(database, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def source_info(path):
    return {"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build(kanjidic: Path, kanjivg: Path) -> tuple[dict, dict]:
    with gzip.open(kanjidic, 'rb') as stream:
        xml = stream.read(MAX_XML + 1)
    entries, header, kd_stats = parse_kanjidic(xml)
    structures, vg_stats = parse_kanjivg(kanjivg)
    database = {"schema_version": 1, "generated": True,
                "sources": {"kanjidic2": {**source_info(kanjidic), **header},
                            "kanjivg": source_info(kanjivg)},
                "entries": merge(entries, structures)}
    validate(database)
    enriched = sum("structure" in e for e in database["entries"].values())
    unresolved = Counter()
    unnamed = 0
    for entry in database["entries"].values():
        if "structure" not in entry:
            continue
        for node in walk(entry["structure"]):
            base = node.get("base", node.get("char"))
            if base is None:
                unnamed += 1
            elif base not in entries:
                unresolved[base] += 1
    stats = {**kd_stats, **vg_stats, "kanjidic2_characters": len(entries),
             "enriched_characters": enriched, "without_structure": len(entries) - enriched,
             "with_frequency": sum("frequency" in e for e in entries.values()),
             "supplementary_characters": sum(ord(c) > 0xFFFF for c in entries),
             "unresolved_components": sum(unresolved.values()),
             "unresolved_bases": dict(sorted(unresolved.items())),
             "unnamed_structural_groups": unnamed,
             "kanjivg_only_characters": len(structures.keys() - entries.keys()),
             "output_bytes": len(encode(database))}
    return database, stats


def write_atomic(path: Path, content: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

