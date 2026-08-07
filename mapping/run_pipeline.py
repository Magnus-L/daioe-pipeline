# %% run_pipeline.py  (project root)
import os, sys, runpy
from pathlib import Path

# (options) choosing model names for estimate_mapping.py
os.environ["MODEL_PRIMARY"] = "gpt-4o"
os.environ["MODEL_SECONDARY"] = "gpt-4o-mini"

# (options) pick year and other parameters for master_pipeline (Eq. 3 etc.)
sys.argv = ["master_pipeline.py", "--year", "2023", "--skip-estimate"]  # lägg till t.ex. "--skip-estimate", "--gamma","1.0","--delta","2.0" vid behov
# Comment: when the mapping matrix 9 x 58 v 2018 has been generated, we can skip the estimation step for faster runs.

# Run the whole pipeline end-to-end (robust even if CWD is not the project root)
ROOT = Path(__file__).resolve().parent
runpy.run_path(str(ROOT / "code" / "master_pipeline.py"), run_name="__main__")
