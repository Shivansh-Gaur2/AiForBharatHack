"""Ensure ml-pipeline root is on sys.path for all tests."""
import pathlib
import sys

_ML_ROOT = str(pathlib.Path(__file__).resolve().parent.parent)
if _ML_ROOT not in sys.path:
    sys.path.insert(0, _ML_ROOT)
