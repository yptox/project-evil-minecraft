#!/usr/bin/env python3
"""
Manifest expansion script for Algorithmic Gallery V2.

Scans high-value model directories, generates manifest entries with emotional tags,
and merges them into the existing curated-props.json.

Run from the project root:
  python3 expand_manifest.py [--dry-run] [--output curated-props.json]
"""

import json
import os
import re
import sys
from pathlib import Path

MODELS_ROOT = Path("Assets/StreamingAssets/models")
MANIFEST_PATH = Path("Assets/StreamingAssets/curated-props.json")

# ---------------------------------------------------------------------------
# 1. Target directories: (glb_dir, group, base_emotional_tags)
# ---------------------------------------------------------------------------
TARGET_DIRS = [
    # ── ORIGINAL (Pass 1) ───────────────────────────────────────────────────
    # Intimate / domestic interiors
    ("l4d2/props_interiors",   "domestic",   ["intimate", "mundane"]),
    ("hl2/props_interiors",    "domestic",   ["intimate", "nostalgic"]),
    ("l4d2/props_furniture",   "furniture",  ["comforting", "domestic"]),
    ("l4d2/props_collectables","item",       ["nostalgic", "personal"]),
    ("dod/props_furniture",    "furniture",  ["comforting", "domestic"]),
    ("tf2/props_hearth",       "domestic",   ["comforting", "nostalgic"]),
    ("tf2/props_medical",      "lab",        ["clinical", "threatening"]),
    ("tf2/props_graveyard",    "item",       ["melancholy", "nostalgic"]),
    ("tf2/props_appliances",   "domestic",   ["mundane", "domestic"]),
    ("l4d2/props_junk",        "workshop",   ["abandoned", "mundane"]),
    ("l4d2/props_downtown",    "retail",     ["public", "mundane"]),
    ("l4d2/props_office",      "office",     ["mundane", "institutional"]),
    ("l4d2/props_lab",         "lab",        ["clinical", "institutional"]),

    # ── PASS 2 ADDITIONS — new vocabulary & broader coverage ────────────────

    # LIMINAL — doors, hallways, transitional architecture
    ("l4d2/props_doors",       "item",       ["liminal", "mundane"]),
    ("dod/props_doors",        "item",       ["liminal", "nostalgic"]),

    # SACRED / ritual / memorial
    ("l4d2/props_cemetery",    "item",       ["sacred", "melancholy"]),

    # BUREAUCRATIC — offices, paperwork, admin tools
    ("portal2/props_office",   "office",     ["bureaucratic", "institutional"]),
    ("tf2/props_office",       "office",     ["bureaucratic", "mundane"]),

    # DECAYED / abandoned — wasteland, rotted environments
    ("hl2/props_canal",        "workshop",   ["decayed", "abandoned", "melancholy"]),
    ("hl2/props_wasteland",    "workshop",   ["decayed", "abandoned"]),
    ("portal2/props_underground","workshop", ["decayed", "abandoned", "threatening"]),
    ("css/props_canal",        "workshop",   ["decayed", "abandoned", "melancholy"]),

    # Threatening / institutional / dystopian (fills the thin "threatening" register)
    ("hl2/props_combine",      "lab",        ["threatening", "institutional", "clinical"]),
    ("css/props_combine",      "lab",        ["threatening", "institutional"]),
    ("portal2/props_basement", "workshop",   ["threatening", "abandoned", "liminal"]),

    # Clinical / lab — broaden beyond TF2 medical
    ("portal2/props_lab",      "lab",        ["clinical", "institutional", "bureaucratic"]),
    ("portal/props_lab",       "lab",        ["clinical", "institutional"]),
    ("hl2/props_lab",          "lab",        ["clinical", "institutional"]),
    ("css/props_lab",          "lab",        ["clinical", "institutional"]),
    ("portal2/props_factory",  "workshop",   ["institutional", "mundane"]),

    # Narrative-loaded one-offs
    ("portal2/props_diorama",  "item",       ["personal", "nostalgic"]),
    ("portal2/props_unique",   "item",       ["personal", "nostalgic"]),
    ("l4d2/props_unique",      "item",       ["personal", "nostalgic"]),

    # Public / institutional architecture
    ("portal2/props_motel",    "retail",     ["public", "abandoned", "mundane"]),
    ("portal2/props_downtown", "retail",     ["public", "mundane"]),
    ("css/props_trainstation", "retail",     ["public", "liminal", "institutional"]),
    ("hl2/props_trainstation", "retail",     ["public", "liminal", "institutional"]),

    # Comforting / nostalgic non-domestic — TF2 thematic maps
    ("tf2/props_diner",        "retail",     ["comforting", "nostalgic", "mundane"]),
    ("tf2/props_camp",         "domestic",   ["comforting", "nostalgic"]),
    ("tf2/props_farm",         "domestic",   ["nostalgic", "comforting", "mundane"]),
    ("tf2/props_manor",        "furniture",  ["nostalgic", "intimate", "comforting"]),
    ("tf2/props_paintings",    "item",       ["personal", "nostalgic"]),
    ("tf2/props_food",         "item",       ["comforting", "mundane"]),

    # Workshop / construction (broaden mundane register)
    ("tf2/props_construction", "workshop",   ["mundane", "abandoned"]),
    ("css/props_industrial",   "workshop",   ["mundane", "institutional"]),
    ("css/props_junk",         "workshop",   ["abandoned", "decayed"]),

    # Wartime / melancholy (DOD untapped)
    ("dod/props_normandy",     "item",       ["melancholy", "abandoned", "nostalgic"]),
    ("dod/props_italian",      "domestic",   ["nostalgic", "melancholy"]),
]

# ---------------------------------------------------------------------------
# 2. Skip patterns — skip files matching these (architectural, effects, etc.)
# ---------------------------------------------------------------------------
SKIP_PATTERNS = [
    r"gib\d*[a-z]?$",       # destruction fragments
    r"_break\d+$",           # breakable variants
    r"_chunk\d*$",
    r"_piece\d*$",
    r"_debris",
    r"attic_beam",
    r"handrail",
    r"conduit_\d",           # raw pipe segments
    r"_trim\d",
    r"_post_",
    r"_underside",
    r"skybox",
    r"^effects",
    r"collision",
    r"^editor",
    r"perftest",
    r"test_",
    r"_lod\d",
    r"_phys$",
    r"^clip_",
    r"_base\d+$",
    r"_upper\d+$",
    r"wall_panel",
    r"_nodraw",
    r"_128$",                 # raw architectural segments
    r"_064$",
    r"_032$",
    r"_256$",
]

SKIP_RE = [re.compile(p, re.IGNORECASE) for p in SKIP_PATTERNS]

def should_skip(stem: str) -> bool:
    for pat in SKIP_RE:
        if pat.search(stem):
            return True
    return False

# ---------------------------------------------------------------------------
# 3. Filename → additional emotional tags
# ---------------------------------------------------------------------------
KEYWORD_EMOTIONAL = [
    # Intimate / personal
    (r"bed|crib|pillow|blanket|mattress|cradle",         ["intimate"]),
    (r"photo|picture|frame|portrait|album",              ["nostalgic", "personal"]),
    (r"toy|doll|teddy|puppet|stuffed",                   ["nostalgic", "personal", "childhood"]),
    (r"book|shelf|bookcase|bookshelf|library",           ["comforting", "nostalgic"]),
    (r"lamp|lantern|candle|light_fixture|nightstand",    ["intimate", "comforting"]),
    (r"couch|sofa|loveseat|armchair",                    ["comforting", "intimate"]),
    (r"bathtub|bath|sink|shower|toilet",                 ["intimate", "mundane"]),
    (r"alarm_clock|clock|watch",                         ["mundane", "personal"]),
    (r"mirror|vanity",                                   ["intimate", "personal"]),
    (r"diary|journal|notebook|calendar",                 ["personal", "nostalgic"]),

    # Nostalgic / memory
    (r"antique|vintage|old|retro|worn",                  ["nostalgic"]),
    (r"suitcase|luggage|bag|backpack",                   ["personal", "nostalgic"]),
    (r"letter|envelope|postcard|mail",                   ["nostalgic", "personal"]),
    (r"piano|guitar|violin|instrument|music",            ["nostalgic", "intimate"]),
    (r"radio|phonograph|gramophone|record",              ["nostalgic", "intimate"]),
    (r"tv|television|monitor|screen",                    ["mundane", "nostalgic"]),

    # Clinical / threatening
    (r"syringe|needle|scalpel|blade|knife|weapon",       ["threatening", "clinical"]),
    (r"morgue|anatomy|specimen|dissect",                 ["clinical", "threatening"]),
    (r"cage|restraint|straitjacket|chains",              ["threatening"]),
    (r"medic|hospital|gurney|stretcher|wheelchair",      ["clinical"]),
    (r"biohazard|hazmat|chemical|toxic",                 ["threatening", "clinical"]),
    (r"operating|surgery|exam",                          ["clinical", "threatening"]),

    # Melancholy / memorial
    (r"grave|coffin|casket|tombstone|hearse|funeral",    ["melancholy"]),
    (r"memorial|monument|shrine|candle_lit",             ["melancholy", "nostalgic"]),
    (r"empty|bare|hollow|broken",                        ["abandoned", "melancholy"]),

    # Abandoned / junk
    (r"trash|garbage|waste|rubbish|junk|debris",         ["abandoned"]),
    (r"rust|decay|rotten|worn|weathered",                ["abandoned", "nostalgic"]),
    (r"cardboard|box|crate|barrel|pallet",               ["abandoned", "mundane"]),

    # Public / institutional
    (r"atm|vending|machine|dispenser",                   ["public", "institutional"]),
    (r"sign|signage|placard|billboard",                  ["public", "mundane"]),
    (r"register|cashregister|counter",                   ["public", "retail"]),
    (r"bench_subway|bench_bus|booth",                    ["public", "mundane"]),
    (r"airport|transit|station|terminal",                ["public", "institutional"]),

    # Mundane / everyday
    (r"table|chair|desk|cabinet|drawer|dresser",         ["mundane", "domestic"]),
    (r"fridge|refrigerator|stove|oven|microwave",        ["mundane", "domestic"]),
    (r"mop|bucket|broom|cleaning",                       ["mundane"]),
    (r"phone|telephone",                                  ["mundane", "personal"]),
    (r"computer|keyboard|monitor|printer|fax",           ["mundane", "institutional"]),

    # Comforting / warmth
    (r"fireplace|hearth|chimney|wood_stove",             ["comforting", "nostalgic"]),
    (r"blanket|quilt|rug|carpet",                        ["comforting", "intimate"]),
    (r"candle|firelight",                                ["comforting", "intimate"]),
    (r"kitchen|cooking|pot|pan|dish",                    ["comforting", "mundane"]),

    # ── PASS 2: New emotional vocabulary ────────────────────────────────────

    # LIMINAL — thresholds, transitional, in-between spaces
    (r"door(?!_handle)|doorway|doorframe",               ["liminal"]),
    (r"hallway|corridor|stairs|stairwell|stairway",      ["liminal"]),
    (r"threshold|archway|gateway|portal_(?!ico)",        ["liminal"]),
    (r"elevator|escalator|ladder|staircase",             ["liminal", "mundane"]),
    (r"window|curtain|blinds(?!ide)",                    ["liminal", "intimate"]),

    # SACRED — ritual, religious, ceremonial
    (r"altar|shrine|cross_(?!hatch)|crucifix|pew",       ["sacred", "melancholy"]),
    (r"church|chapel|cathedral|religious|holy",          ["sacred"]),
    (r"statue(?!ttes)|idol|relic|icon_",                 ["sacred", "nostalgic"]),
    (r"prayer|votive|offering|incense",                  ["sacred", "intimate"]),

    # BUREAUCRATIC — paperwork, admin, records
    (r"filing|file_cabinet|filecabinet|folder|binder",   ["bureaucratic", "institutional"]),
    (r"clipboard|paperwork|document|form_|forms_",       ["bureaucratic", "institutional"]),
    (r"stamp|ledger|receipt|invoice|paperstack",         ["bureaucratic", "mundane"]),
    (r"papers|paperwall|paperstack|paperpile",           ["bureaucratic", "mundane"]),
    (r"typewriter|adding_machine|register_",             ["bureaucratic", "nostalgic"]),

    # DECAYED — rotted, ruined, fallen-apart variants
    (r"rotted|rotten|decayed|crumbling|collapsed",       ["decayed", "abandoned"]),
    (r"ruined|wrecked|burnt|burned|charred",             ["decayed", "abandoned"]),
    (r"corroded|tarnished|moldy|moldering|mossy",        ["decayed", "abandoned"]),
    (r"rusted|rusty|rust_",                              ["decayed", "abandoned"]),

    # Refinement: photo/portrait now also personal+intimate (memory objects)
    (r"family_photo|family_portrait|wedding",            ["personal", "intimate", "nostalgic"]),
]

KEYWORD_RE = [(re.compile(p, re.IGNORECASE), tags) for p, tags in KEYWORD_EMOTIONAL]

def get_emotional_tags_from_name(stem: str) -> list:
    found = set()
    for pat, tags in KEYWORD_RE:
        if pat.search(stem):
            found.update(tags)
    return sorted(found)

# ---------------------------------------------------------------------------
# 4. Visual tag heuristics from filename (preserve existing tag conventions)
# ---------------------------------------------------------------------------
def guess_size_tag(stem: str) -> str:
    large_kw = r"large|big|heavy|grand|double|king|queen|full|wide|long|wardrobe|armoire|cabinet|bookcase|sofa|couch|bed|table|refrigerator|stove|washer|dryer"
    small_kw = r"small|tiny|mini|micro|glass|cup|mug|plate|book|bottle|can|jar|pen|pencil|phone|remote|key|coin|pill|syringe|alarm_clock|candle"
    if re.search(large_kw, stem, re.I):
        return "large"
    if re.search(small_kw, stem, re.I):
        return "small"
    return "medium"

def guess_color_tag(stem: str) -> str:
    warm_kw = r"wood|oak|pine|maple|red|orange|yellow|gold|amber|warm|hearth|fire|candle|bronze|copper"
    cool_kw = r"steel|metal|iron|chrome|blue|silver|white|cold|clinical|glass|plastic|computer|tech"
    dark_kw = r"black|dark|night|shadow|ebony"
    if re.search(dark_kw, stem, re.I):
        return "dark"
    if re.search(warm_kw, stem, re.I):
        return "warm"
    if re.search(cool_kw, stem, re.I):
        return "cool"
    return "neutral"

# ---------------------------------------------------------------------------
# 5. Display name cleanup
# ---------------------------------------------------------------------------
def make_display_name(stem: str) -> str:
    # Remove numeric suffixes like 01a, _02, etc.
    name = re.sub(r'[_\-]?0*\d+[a-z]?$', '', stem)
    name = name.replace('_', ' ').replace('-', ' ').strip()
    return name.title()

# ---------------------------------------------------------------------------
# 6. ID generation
# ---------------------------------------------------------------------------
def make_id(source_dir: str, stem: str) -> str:
    prefix = source_dir.replace('/', '_').replace('-', '_')
    return f"{prefix}_{stem}".lower()

# ---------------------------------------------------------------------------
# 7. Main expansion logic
# ---------------------------------------------------------------------------
def expand_manifest(dry_run: bool = False):
    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    existing_paths = {p["glb_path"] for p in manifest["props"]}
    existing_ids = {p["id"] for p in manifest["props"]}
    new_entries = []
    skipped = 0
    already_exists = 0

    for source_dir, group, base_emotional in TARGET_DIRS:
        dir_path = MODELS_ROOT / source_dir
        if not dir_path.exists():
            print(f"  [WARN] Directory not found: {dir_path}")
            continue

        glb_files = sorted(dir_path.glob("*.glb"))
        dir_added = 0

        for glb_file in glb_files:
            stem = glb_file.stem
            rel_path = f"{source_dir}/{glb_file.name}"

            if rel_path in existing_paths:
                already_exists += 1
                continue

            if should_skip(stem):
                skipped += 1
                continue

            entry_id = make_id(source_dir, stem)
            if entry_id in existing_ids:
                already_exists += 1
                continue

            # Build tags
            size_tag = guess_size_tag(stem)
            color_tag = guess_color_tag(stem)
            emotional = get_emotional_tags_from_name(stem)
            extra_emotional = [t for t in base_emotional if t not in emotional]
            emotional_tags = sorted(set(emotional + extra_emotional))

            tags = ["matte", color_tag, size_tag]

            entry = {
                "id": entry_id,
                "glb_path": rel_path,
                "display_name": make_display_name(stem),
                "group": group,
                "category": source_dir.split('/')[-1],
                "tags": tags,
                "emotional_tags": emotional_tags,
                "poly_count": 0,      # unknown without loading the mesh
                "dimensions": {"x": 0.0, "y": 0.0, "z": 0.0},
            }

            new_entries.append(entry)
            existing_ids.add(entry_id)
            existing_paths.add(rel_path)
            dir_added += 1

        print(f"  {source_dir}: +{dir_added} props")

    print(f"\nSummary:")
    print(f"  Existing props:    {len(manifest['props'])}")
    print(f"  Already covered:   {already_exists}")
    print(f"  Skipped (noise):   {skipped}")
    print(f"  New props to add:  {len(new_entries)}")
    print(f"  New total:         {len(manifest['props']) + len(new_entries)}")

    if dry_run:
        print("\n[DRY RUN] No changes written.")
        # Print a sample
        print("\nSample new entries:")
        for e in new_entries[:5]:
            print(json.dumps(e, indent=2))
        return

    # Also backfill emotional_tags on existing props that have none
    backfilled = 0
    for prop in manifest["props"]:
        if "emotional_tags" not in prop:
            stem = Path(prop["glb_path"]).stem
            base = []
            # infer from existing group
            group_defaults = {
                "domestic": ["intimate", "mundane"],
                "furniture": ["comforting", "domestic"],
                "item": ["mundane", "personal"],
                "lab": ["clinical", "institutional"],
                "office": ["mundane", "institutional"],
                "retail": ["public", "mundane"],
                "tech": ["mundane", "institutional"],
                "workshop": ["mundane"],
            }
            base = group_defaults.get(prop.get("group", ""), [])
            from_name = get_emotional_tags_from_name(stem)
            prop["emotional_tags"] = sorted(set(base + from_name))
            backfilled += 1

    manifest["props"].extend(new_entries)
    print(f"  Backfilled emotional_tags on {backfilled} existing props.")

    output_path = "--output" in sys.argv and sys.argv[sys.argv.index("--output") + 1] or MANIFEST_PATH
    with open(output_path, 'w') as f:
        json.dump(manifest, f, separators=(',', ':'))

    print(f"\nWritten to: {output_path}")
    print(f"Final manifest: {len(manifest['props'])} props")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    print(f"{'[DRY RUN] ' if dry_run else ''}Expanding manifest...")
    os.chdir(Path(__file__).parent / "Assets/StreamingAssets" / "../..")
    # Change to project dir so relative paths work
    os.chdir(Path(__file__).parent)
    expand_manifest(dry_run)
