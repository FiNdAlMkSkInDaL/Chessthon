"""Stage remaining_our cap variants from the submitted zip.

One variable: the cap on remaining_our. No dynamic ID, no HEAD stew.
Parent default: the signer archive (not in git) (byte-identical to signer last-good).
"""

from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_ZIP = ROOT / "dist" / "agent.zip"
REPO_ZIP = ROOT / "dist" / "agent.zip"
ANCHOR = "    remaining_our = _clamp((PLY_CAP - game_ply + 1) // 2, 1, 40)\n"

VARIANTS: dict[str, str] = {
    "cap40": ANCHOR,
    "cap30": "    remaining_our = _clamp((PLY_CAP - game_ply + 1) // 2, 1, 30)\n",
    "cap25": "    remaining_our = _clamp((PLY_CAP - game_ply + 1) // 2, 1, 25)\n",
    "cap20": "    remaining_our = _clamp((PLY_CAP - game_ply + 1) // 2, 1, 20)\n",
    "early24": (
        "    horizon = (PLY_CAP - game_ply + 1) // 2\n"
        "    cap = 24 if game_ply < 80 else 40\n"
        "    remaining_our = _clamp(horizon, 1, cap)\n"
    ),
}


def parent_zip(explicit: Path | None = None) -> Path:
    if explicit is not None:
        path = explicit.expanduser().resolve()
        if not path.is_file():
            raise SystemExit(f"parent zip missing: {path}")
        return path
    for path in (ARCHIVE_ZIP, REPO_ZIP, ROOT / "dist" / "last-good.zip"):
        if path.is_file():
            return path
    raise SystemExit("no submitted agent.zip / dist/last-good.zip")


def unpack_parent(dst: Path, zpath: Path | None = None) -> Path:
    zpath = parent_zip(zpath)
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    with zipfile.ZipFile(zpath) as archive:
        archive.extractall(dst)
    if not (dst / "agent.py").is_file():
        raise SystemExit(f"{zpath} has no agent.py at zip root")
    text = (dst / "time_nb.py").read_text(encoding="utf-8")
    if "early_stop_ok" in text or "soft_budget" in text:
        raise SystemExit("refusing stew parent: dynamic ID helpers in time_nb")
    if ANCHOR not in text:
        raise SystemExit("parent time_nb remaining_our cap-40 anchor missing")
    print(f"parent {zpath} -> {dst}")
    return dst


def stage_one(src: Path, dst: Path, body: str) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    path = dst / "time_nb.py"
    text = path.read_text(encoding="utf-8")
    if ANCHOR not in text:
        raise SystemExit(f"{dst.name}: cap-40 anchor missing")
    path.write_text(text.replace(ANCHOR, body, 1), encoding="utf-8")
    print(f"staged {dst.name}")


def stage_all(
    out: Path, *, parent_path: Path | None = None, only: str | None = None
) -> Path:
    parent = unpack_parent(out / "_parent", parent_path)
    names = [only] if only else list(VARIANTS)
    for name in names:
        if name not in VARIANTS:
            raise SystemExit(f"unknown variant {name}; have {', '.join(VARIANTS)}")
        stage_one(parent, out / name, VARIANTS[name])
    return parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage remaining_our cap variants.")
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "dist" / "clock_candidates",
    )
    parser.add_argument(
        "--parent",
        type=Path,
        default=None,
        help="zip to unpack (signer: dist/last-good.zip). Default: the signer archive then repo.",
    )
    parser.add_argument(
        "--only",
        choices=sorted(VARIANTS),
        default=None,
        help="stage one variant instead of all five",
    )
    args = parser.parse_args()
    stage_all(args.out, parent_path=args.parent, only=args.only)


if __name__ == "__main__":
    main()
