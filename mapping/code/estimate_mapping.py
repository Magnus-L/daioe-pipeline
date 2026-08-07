""" 
estimate_mapping.py — LLM-based scoring of application–ability relatedness (9×58)

Purpose (non-programmer summary):
- Reads our applications, abilities/skills, and anchor examples.
- Prompts a language model to rate how strongly each application relates to each ability/skill (0..1).
- Produces a 9×58 mapping matrix saved to output/, used by downstream steps.

Expected inputs:
- raw_data/applications.csv (ai_app_id, name)
- raw_data/abilities.csv (ability_id, ability_name, ability_definition)
- raw_data/anchors.csv (from Step 1; high/low examples per ability)

Expected output:
- output/mapping_matrix_9x58_v{vantage}.csv

How this file is called:
- `code/master_pipeline.py` calls `estimate_mapping.py` via `run_estimate_mapping(...)`.
- If estimation fails, the pipeline tries to continue using a previously saved matrix.
"""

# %% ----------- Direct to relative project folders -----------
from pathlib import Path
import os, json, time, argparse
import pandas as pd, numpy as np

# Project root = parent of this script's folder
ROOT = Path(__file__).resolve().parents[1]
raw_dir  = ROOT / "raw_data"
mod_dir  = ROOT / "mod_data"
out_dir  = ROOT / "output"
for p in (raw_dir, mod_dir, out_dir):
    p.mkdir(exist_ok=True)

# -------- Helpers --------
SYSTEM_PROMPT = """You are an expert occupational AI capability mapper.
Goal: score relatedness r ∈ [0,1] between ONE AI application and ONE human ability (from a 58-ability list: 52 O*NET + 6 social skills).
Scale:
- 0.00 = no support for the ability’s core tasks
- 0.25 = weak/indirect support
- 0.50 = moderate support on several core sub-tasks
- 0.75 = strong support on many core sub-tasks
- 1.00 = AI can execute most core sub-tasks at frontier level
Consider: task decomposition, codifiability, input/output modality, data needs, robustness to context, need for social/interactive judgement, failure modes.
Edge cases: count only what the application itself enables; multi-modal counts only if the modality is core for the ability.
Return JSON: {"r": float, "rationale": "...", "confidence": "low|medium|high", "flags": []}"""

USER_PROMPT = """CONTEXT (vantage={vantage}):
Score relatedness between the AI application and the human ability below. Return JSON only.

AI APPLICATION
name: {application_name}
definition: {application_definition}

HUMAN ABILITY
name: {ability_name}
definition: {ability_definition}

ANCHORS
high_examples: {anchors_high}
low_examples: {anchors_low}
"""

# Plain-English: Function `read_inputs` — see module docstring for overall workflow context.
def read_inputs():
    apps = pd.read_csv(raw_dir / "applications.csv")
    abilities = pd.read_csv(raw_dir / "abilities.csv")
    # anchors.csv with columns: ai_app_id, ability_id, label (high/low), note
    anchors_path = raw_dir / "anchors.csv"
    anchors = pd.read_csv(anchors_path) if anchors_path.exists() else pd.DataFrame(columns=["ai_app_id","ability_id","label","note"])
    # create numeric app ids if not present
    if "ai_app_id" not in apps.columns:
        apps = apps.assign(ai_app_id=range(1, len(apps)+1))
    return apps, abilities, anchors

# Plain-English: Function `build_prompt` — see module docstring for overall workflow context.
def build_prompt(app, ab, anchors_high, anchors_low, vantage="2018"):
    return USER_PROMPT.format(
        vantage=vantage,
        application_name=app["name"],
        application_definition=app.get("short_definition","").strip(),
        ability_name=ab["ability_name"],
        ability_definition=ab.get("ability_definition","").strip(),
        anchors_high=json.dumps(anchors_high, ensure_ascii=False),
        anchors_low=json.dumps(anchors_low, ensure_ascii=False),
    )

# Plain-English: Function `call_llm` — see module docstring for overall workflow context.
def call_llm(model, sys, usr, temperature=0.2):
    # This function assumes openai SDK is installed in your environment.
    # We don't call it here inside this notebook, but it's ready to go.
    from openai import OpenAI
    client = OpenAI()
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role":"system","content":sys},{"role":"user","content":usr}],
        response_format={"type":"json_object"},
        temperature=temperature,
    )
    return json.loads(resp.choices[0].message.content)

# Plain-English: Function `main` — see module docstring for overall workflow context.
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vantage", default="2018")
    ap.add_argument("--model_primary", default=os.getenv("MODEL_PRIMARY","gpt-4o"))
    ap.add_argument("--model_secondary", default=os.getenv("MODEL_SECONDARY","gpt-4o-mini"))
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--sleep", type=float, default=0.2, help="Sleep between calls to avoid rate limits.")
    ap.add_argument("--max_pairs", type=int, default=0, help="If >0, limit the number of (app,ability) pairs for a dry-run.")
    args = ap.parse_args()

    apps, abilities, anchors = read_inputs()

    # Precompute anchors per app
    # expected columns in anchors: ai_app_id, ability_id, label in {high,low}, note
    anchors_by_app = {}
    for app_id, sub in anchors.groupby("ai_app_id"):
        anchors_by_app[app_id] = {
            "high": sub[sub["label"].str.lower()=="high"][["ability_id","note"]].to_dict(orient="records"),
            "low":  sub[sub["label"].str.lower()=="low"][["ability_id","note"]].to_dict(orient="records"),
        }

    rows = []
    total = len(apps) * len(abilities)
    count = 0

    for _, app in apps.iterrows():
        app_id = int(app["ai_app_id"])
        app_anchors = anchors_by_app.get(app_id, {"high": [], "low": []})
        # Take a small subset of anchors to keep prompts short
        high_examples = app_anchors["high"][:5]
        low_examples  = app_anchors["low"][:5]

        for __, ab in abilities.iterrows():
            count += 1
            if args.max_pairs and count > args.max_pairs:
                break
            prompt = build_prompt(app, ab, high_examples, low_examples, vantage=args.vantage)
            rec = {"ai_app_id": app_id, "ability_id": int(ab["ability_id"]), "app_name": app["name"], "ability_name": ab["ability_name"]}
            try:
                out1 = call_llm(args.model_primary, SYSTEM_PROMPT, prompt)
                time.sleep(args.sleep)
                out2 = call_llm(args.model_secondary, SYSTEM_PROMPT, prompt)
                r1, r2 = float(out1.get("r",0.0)), float(out2.get("r",0.0))
                rec.update({
                    "r_primary": r1,
                    "r_secondary": r2,
                    "r_mean": max(0.0, min(1.0, (r1+r2)/2.0)),
                    "conf_primary": out1.get("confidence",""),
                    "conf_secondary": out2.get("confidence",""),
                })
            except Exception as e:
                rec.update({"error": str(e), "r_mean": np.nan})
            rows.append(rec)

    scores = pd.DataFrame(rows)
    scores_path = mod_dir / f"mapping_scores_v{args.vantage}.csv"
    scores.to_csv(scores_path, index=False)

    # Pivot to a 9×58 matrix
    mat = scores.pivot_table(index="ai_app_id", columns="ability_id", values="r_mean", aggfunc="mean")
    mat_path = out_dir / f"mapping_matrix_9x58_v{args.vantage}.csv"
    mat.to_csv(mat_path)

    # Save a simple run report
    report = {
        "vantage": args.vantage,
        "pairs_evaluated": len(scores),
        "apps": len(apps),
        "abilities": len(abilities),
        "models": {"primary": args.model_primary, "secondary": args.model_secondary},
        "sleep": args.sleep,
    }
    (out_dir / f"run_report_v{args.vantage}.json").write_text(json.dumps(report, indent=2))

    print("Saved:", scores_path)
    print("Saved:", mat_path)

if __name__ == "__main__":
    main()