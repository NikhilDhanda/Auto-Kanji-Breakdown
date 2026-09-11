"""Development CLI for the shared, Python 3.9-compatible database builder."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.akb.build_data import *  # Re-export the existing tooling API.
from src.akb.data_store import manifest

def default_source(name):
    """Keep upstream inputs in the dedicated source directory, never at root."""
    return ROOT / "data_sources" / name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kanjidic", type=Path, default=default_source("kanjidic2.xml.gz"))
    parser.add_argument("--kanjivg", type=Path, default=default_source("kanjivg-20250816-main.zip"))
    parser.add_argument("--output", type=Path, default=ROOT / "generated/kanji_db.json")
    parser.add_argument("--stats", type=Path, default=ROOT / "generated/build-stats.json")
    parser.add_argument("--manifest", type=Path, help="Sidecar path (default: manifest.json beside output)")
    args = parser.parse_args()
    sidecar = args.manifest or args.output.with_name('manifest.json')
    inputs = {args.kanjidic.resolve(), args.kanjivg.resolve()}
    outputs = {args.output.resolve(), args.stats.resolve(), sidecar.resolve()}
    if inputs & outputs or len(outputs) != 3 or any("data_sources" in p.parts for p in outputs):
        parser.error("Outputs must be distinct and must not overwrite upstream sources")
    try:
        database, stats = build(args.kanjidic, args.kanjivg)
        write_atomic(args.output, encode(database))
        write_atomic(args.stats, encode(stats))
        write_atomic(sidecar, encode(manifest(database, encode(database))))
    except (OSError, ValueError, ET.ParseError, zipfile.BadZipFile) as error:
        parser.exit(1, f"Database build failed: {error}\n")
    print(json.dumps(stats, ensure_ascii=True, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
