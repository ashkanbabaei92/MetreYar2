# MetreYar2 — Python Characterization Tests
#
# Usage:
#   Generate golden master:  GENERATE=1 pytest tests/char_python/ -v
#   Run comparison:          pytest tests/char_python/ -v
#   Run single test:         GENERATE=1 pytest tests/char_python/test_revit_parse.py::test_T01_R1_simple -v
#
# Requirements: Python 3.10+, pytest, pandas, streamlit, xlsxwriter, openpyxl
# Note: No production files are modified by these tests.
