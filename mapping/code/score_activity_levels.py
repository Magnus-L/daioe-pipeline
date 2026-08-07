"""
score_activity_levels.py — how far up each social activity can an AI application actually get?

The problem this fixes
----------------------
The mapping matrix scores one undifferentiated number per (application, activity). So
"Interpreting the Meaning of Information for Others" gets AI reach 0.49 whether the occupation needs
a call-centre agent explaining a billing statement or a pastor interpreting scripture, and
"Assisting and Caring for Others" gets one number whether the task is helping a coworker with an
assignment or counselling someone who is suicidal. Difficulty is thrown away, and it is exactly what
separates the two.

O*NET already carries the missing information twice over. Each occupation has a **required level**
per activity (1-7, currently collapsed into the Level x Importance product and lost when we take
shares), and O*NET publishes **anchored examples** fixing what each level means:

    Assisting and Caring for Others
      level 2  Help a coworker complete an assignment
      level 4  Assist a stranded traveler in finding lodging
      level 6  Care for seriously injured persons in an emergency room

So the right question is not "does AI support this activity" but "how far up this scale does AI
reliably get", which is the same threshold logic the measure already applies to benchmarks against a
human anchor. Occupation o is exposed on activity j to the extent the attained level clears its
required level; clergy requires 4.90 on caring and customer service 2.51, and that difference is the
whole story the current construction cannot tell.

What this file produces
-----------------------
`attained_level` in 1-7 per (application, activity), with the O*NET anchors in the prompt, plus a
`ceiling_reason` naming what stops it going higher. Replicates rotate the anchor window as before,
so the spread measures sensitivity rather than decoding noise.

Deliberate conservatism, and why
--------------------------------
The scorer is told to judge *reliable, unsupervised* performance and to treat consequential failure
as disqualifying. That is not squeamishness: an exposure measure claims an occupation's work can be
done at a given standard, and for activities whose top anchors are emergency-room care or crisis
support, a system that is usually right is not performing the activity at that level. DAIOE also
already computes `conseq_error` per occupation and leaves its discount disabled; this keeps the
scoring honest on the same dimension at the activity end.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

MAP = Path(__file__).resolve().parents[1]
ROOT = MAP.parent
RAW, MOD, OUT = MAP / "raw_data", MAP / "mod_data", MAP / "output"

MODEL = "claude-opus-5"

LEVEL_SCHEMA = {
    "type": "object",
    "properties": {
        "attained_level": {"type": "number",
                           "description": "Highest level on the 1-7 anchored scale the application "
                                          "reliably performs unsupervised. May be fractional."},
        "ceiling_reason": {"type": "string",
                           "description": "What stops it going higher. One sentence, concrete."},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": ["attained_level", "ceiling_reason", "confidence"],
    "additionalProperties": False,
}

RUBRIC = """You judge how far up a work-activity scale an AI application can reliably get.

O*NET rates every occupation's requirement for a work activity on a level scale from 1 to 7, with
published anchor examples fixing what the numbers mean. You are given those anchors. Report the
highest level at which the application performs the activity **reliably and unsupervised**, in the
sense that an employer could substitute it for the human doing that level of the work.

Judge the application as defined, not the field it belongs to and not what it may become.

Two things set the ceiling, and both bind:

1. Capability. Can it actually do work of that difficulty, on the inputs that work involves?
2. Consequence of failure. At levels whose anchors describe consequential work, being usually right
   is not performing the activity. If a failure would seriously harm someone and the system cannot
   be left unsupervised, the activity is not attained at that level, however fluent the output.

Do not reward fluency. Producing text that resembles what an expert would say is not the same as
performing the activity: an application that can discuss a task but could not be handed
responsibility for it has not attained that level.

Report a level between 1 and 7. Fractional values are fine. If the application does nothing for this
activity even at level 1, report 1 and say so."""


def build_anchor_text(anchors: pd.DataFrame, element_id: str) -> str:
    g = anchors[anchors["Element ID"] == element_id].sort_values("Anchor Value")
    return "\n".join(f"  level {int(r['Anchor Value'])}: {r['Anchor Description']}"
                     for _, r in g.iterrows())


def build_requests(apps, acts, anchors, replicates, effort, max_tokens):
    import importlib.util
    spec = importlib.util.spec_from_file_location("emc", MAP / "code" / "estimate_mapping_claude.py")
    emc = importlib.util.module_from_spec(spec)
    sys.modules["emc"] = emc
    spec.loader.exec_module(emc)
    mapping_anchors = pd.read_csv(RAW / "anchors_v2.csv")

    reqs = []
    for rep in range(replicates):
        for _, app in apps.iterrows():
            # Reuse the calibration block: it fixes where this application sits overall, which is
            # what stops the level judgement drifting application by application.
            sysblocks = [
                {"type": "text", "text": RUBRIC},
                {"type": "text",
                 "text": (f"AI APPLICATION\nname: {app['name']}\ndefinition: {app['short_definition']}\n\n"
                          f"CALIBRATION (expert scores for this application, Felten, Raj and Seamans 2018)\n"
                          f"{emc._anchor_block(mapping_anchors, int(app['ai_app_id']), rep)}"),
                 "cache_control": {"type": "ephemeral", "ttl": "1h"}},
            ]
            for _, act in acts.iterrows():
                user = (f"WORK ACTIVITY\nname: {act['ability_name']}\n"
                        f"definition: {act['ability_definition']}\n\n"
                        f"O*NET LEVEL ANCHORS\n{build_anchor_text(anchors, act['element_id'])}\n\n"
                        f"What level does this application reliably attain?")
                reqs.append({
                    "custom_id": f"a{int(app['ai_app_id'])}_b{int(act['ability_id'])}_r{rep}",
                    "params": {"model": MODEL, "max_tokens": max_tokens, "system": sysblocks,
                               "messages": [{"role": "user", "content": user}],
                               "output_config": {"effort": effort,
                                                 "format": {"type": "json_schema", "schema": LEVEL_SCHEMA}}},
                })
    return reqs


def collect_levels(emc, batch_id: str) -> pd.DataFrame:
    """Parse the level schema.

    The generic collector in `estimate_mapping_claude` reads a key called `r` and clips it to
    [0, 1], which is right for a relatedness score and silently wrong here: this schema returns
    `attained_level` on O*NET's 1-7 scale, so every response parsed to NaN while reporting zero
    errors. Batch results are retained, so the fix costs nothing but it is worth the separate
    function rather than overloading the other one.
    """
    import json
    import time

    import numpy as np

    client = emc._client()
    while True:
        b = client.messages.batches.retrieve(batch_id)
        if b.processing_status == "ended":
            break
        time.sleep(30)

    rows = []
    for res in client.messages.batches.results(batch_id):
        app_id, element_id, rep = (int(p[1:]) for p in res.custom_id.split("_"))
        row = {"ai_app_id": app_id, "ability_id": element_id, "replicate": rep,
               "attained_level": np.nan, "ceiling_reason": "", "confidence": "", "error": ""}
        if res.result.type == "succeeded":
            text = next((x.text for x in res.result.message.content if x.type == "text"), "")
            try:
                p = json.loads(text)
                row["attained_level"] = float(np.clip(float(p["attained_level"]), 1.0, 7.0))
                row["ceiling_reason"] = str(p.get("ceiling_reason", ""))
                row["confidence"] = str(p.get("confidence", ""))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                row["error"] = f"parse: {exc}"
        else:
            row["error"] = str(getattr(res.result, "error", res.result.type))
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--block", default="activity",
                    help="comma-separated element blocks from abilities_v2.csv: "
                         "activity, ability, social_skill. All 75 elements are anchored by O*NET.")
    ap.add_argument("--tag", default="", help="output suffix; defaults to the block list")
    ap.add_argument("--replicates", type=int, default=3)
    ap.add_argument("--effort", default="high")
    ap.add_argument("--max-tokens", type=int, default=4000)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--submit", action="store_true")
    g.add_argument("--collect", metavar="BATCH_ID")
    args = ap.parse_args()

    import importlib.util
    spec = importlib.util.spec_from_file_location("emc", MAP / "code" / "estimate_mapping_claude.py")
    emc = importlib.util.module_from_spec(spec)
    sys.modules["emc"] = emc
    spec.loader.exec_module(emc)

    apps = pd.read_csv(RAW / "applications_v2.csv")
    els = pd.read_csv(RAW / "abilities_v2.csv")
    blocks = [b.strip() for b in args.block.split(",")]
    unknown = set(blocks) - set(els.block.unique())
    if unknown:
        raise SystemExit(f"unknown block(s) {sorted(unknown)}; have {sorted(els.block.unique())}")
    acts = els[els.block.isin(blocks)]
    tag = args.tag or "_".join(blocks)
    anchors = pd.read_excel(ROOT / "data" / "raw" / "onet_level_scale_anchors.xlsx")
    anchors.columns = [c.strip() for c in anchors.columns]

    if args.collect:
        scores = collect_levels(emc, args.collect)
        scores.to_csv(MOD / f"levels_raw_{tag}.csv", index=False)
        cell = scores[scores.attained_level.notna()].groupby(["ai_app_id", "ability_id"]).agg(
            level=("attained_level", "median"), lo=("attained_level", "min"),
            hi=("attained_level", "max"), n=("attained_level", "size")).reset_index()
        cell["range"] = cell.hi - cell.lo
        cell.to_csv(MOD / f"levels_cells_{tag}.csv", index=False)
        cell.pivot(index="ai_app_id", columns="ability_id", values="level").to_csv(
            OUT / f"levels_matrix_{tag}.csv")
        print(f"cells {len(cell)}  errors {int(scores.error.astype(bool).sum())}  "
              f"median replicate range {cell['range'].median():.2f}")
        return

    reqs = build_requests(apps, acts, anchors, args.replicates, args.effort, args.max_tokens)
    if args.dry_run:
        print(json.dumps(emc.estimate_cost(reqs, batch=True), indent=2))
        print("\n--- first request ---")
        for b in reqs[0]["params"]["system"]:
            print(b["text"][:1100]); print("  " + "." * 60)
        print(reqs[0]["params"]["messages"][0]["content"])
        return
    emc.submit_batch(reqs, {"model": MODEL, "effort": args.effort, "replicates": args.replicates,
                            "tag": tag, "kind": "element_levels", "blocks": blocks})


if __name__ == "__main__":
    main()
