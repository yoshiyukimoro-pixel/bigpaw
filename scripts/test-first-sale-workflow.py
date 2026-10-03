#!/usr/bin/env python3
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).resolve().parents[1]/'app/backend/first_sale_workflow_test.py'),run_name='__main__')
