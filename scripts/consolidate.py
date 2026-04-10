#!/usr/bin/env python3
"""Consolidates all extracted Dhamma point files into a single master database markdown file."""

from pathlib import Path


def main():
    extracted_dir = Path("output/extracted")
    master_file = Path("master_dhamma_database.md")

    if not extracted_dir.exists():
        print("Error: 'extracted' directory not found.")
        return

    md_files = list(extracted_dir.glob("*.md"))
    if not md_files:
        print("No extracted files found to consolidate.")
        return

    print(f"Consolidating {len(md_files)} files...")

    with open(master_file, "w", encoding="utf-8") as outfile:
        outfile.write("# Master Dhamma Points Database\n\n")

        # Sort alphabetically to keep chronological order if files are numbered
        for file_path in sorted(md_files):
            outfile.write(f"## Source: {file_path.name}\n\n")
            with open(file_path, "r", encoding="utf-8") as infile:
                outfile.write(infile.read().strip())
            outfile.write("\n\n---\n\n")

    print(f"Success! Master database created/updated at '{master_file.name}'")


if __name__ == "__main__":
    main()


#! TODO: we need sort data according to tags
