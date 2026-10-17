"""
Cleanup utility to remove all temporary Vercel deployment files
before deploying to IBM LinuxONE.

Usage:
    python scripts/clean_vercel.py
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FILES_TO_REMOVE = [
    ROOT / "vercel.json",
    ROOT / "TraceGuard-Frontend" / "vercel.json",
    ROOT / ".vercel",
    ROOT / "TraceGuard-Frontend" / ".vercel",
]

removed_count = 0
for target in FILES_TO_REMOVE:
    if target.is_dir():
        shutil.rmtree(target, ignore_errors=True)
        print(f"Removed directory: {target.relative_to(ROOT)}")
        removed_count += 1
    elif target.is_file():
        target.unlink(missing_ok=True)
        print(f"Removed file: {target.relative_to(ROOT)}")
        removed_count += 1

if removed_count == 0:
    print("No Vercel temporary files found. Project is already clean.")
else:
    print(f"\nSuccessfully removed {removed_count} Vercel-specific file(s).")
    print("Project is clean and ready for IBM LinuxONE deployment.")
