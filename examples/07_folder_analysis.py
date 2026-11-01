"""Analyse every photo of a folder (settings tuned on the first photo).

Run:  python 07_folder_analysis.py photos/mysample
Writes output/folder/<folder name>/results.csv and parameters.json
interactive=True would show the first photo and ask "Is this okay?".
"""
import sys

from line_finder import main_folder

folder = sys.argv[1] if len(sys.argv) > 1 else "photos/mysample"
rows = main_folder(folder, "output", interactive=False, show=False)
print(f"{len(rows)} photos analysed")
