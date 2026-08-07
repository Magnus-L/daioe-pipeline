"""
estimate_mapping_claude.py — score the application x ability mapping matrix with Claude.

Replaces `estimate_mapping.py` (OpenAI, gpt-4o + gpt-4o-mini, October 2018 vantage). The published
matrix that file produced stays exactly where it is; this writes a new vintage alongside it.

Four changes from the original, each with a reason
--------------------------------------------------

1. `temperature` is gone, not translated. Claude Opus 5 rejects `temperature`, `top_p` and `top_k`
   with a 400. The original set temperature=0.2. Run-to-run variation therefore has to come from
   somewhere real rather than from decoding noise, which is the point of (2).

2. Replicates instead of a two-model average. The original averaged a strong scorer (gpt-4o) with a
   weak one (gpt-4o-mini), which is variance reduction bought with bias: the mean is pulled toward
   the weaker judge. Here one strong model scores each cell several times, each replicate seeing a
   different rotation of that application's calibration anchors, and we take the median. The spread
   across replicates is kept, and it measures something worth measuring: whether a cell's score
   survives a change of calibration exemplars. Cells with wide spread are cells the matrix does not
   really determine.

3. Structured outputs instead of parsing. `output_config.format` validates the response against a
   JSON schema at the API layer, so the free-text parse and its failure path disappear.

4. Prompt caching and the Batch API. The rubric and the application block are byte-identical across
   that application's 58 ability calls, so they cache; nothing here is latency-sensitive, so the
   batch endpoint halves the token price.

Usage
-----
    python code/estimate_mapping_claude.py --dry-run            # build requests, cost, no API call
    python code/estimate_mapping_claude.py --sync --limit 40    # small synchronous calibration run
    python code/estimate_mapping_claude.py --submit             # submit the full batch
    python code/estimate_mapping_claude.py --collect BATCH_ID   # gather results and aggregate

Credentials: ANTHROPIC_API_KEY, or an `ant auth login` profile. Nothing here reads register data;
the payload is public O*NET ability definitions plus our own application definitions (green zone).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, MOD, OUT = ROOT / "raw_data", ROOT / "mod_data", ROOT / "output"
for _p in (MOD, OUT):
    _p.mkdir(exist_ok=True)

MODEL = "claude-opus-5"
VANTAGE = "2026"

# Anchors are built k=8 deep per direction; each replicate shows a rotation of SHOW_ANCHORS of them.
# Rotation is deterministic (no RNG), so a run is reproducible from its replicate index alone.
SHOW_ANCHORS = 5

SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "r": {"type": "number", "description": "Relatedness in [0,1]."},
        "rationale": {"type": "string", "description": "One or two sentences. State the mechanism, not a restatement of the score."},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": ["r", "rationale", "confidence"],
    "additionalProperties": False,
}

# Note on the schema: JSON-schema numerical constraints (minimum/maximum) are not enforced by
# structured outputs, so `r` is clamped to [0,1] on collection rather than declared bounded here.

RUBRIC = """You score how strongly one AI application supports one human ability.

Return r in [0,1]:
  0.00  the application does nothing for this ability's core tasks
  0.25  weak or indirect support
  0.50  moderate support on several core sub-tasks
  0.75  strong support on many core sub-tasks
  1.00  the application can execute most of this ability's core sub-tasks at frontier level

Judge the application as defined, not the field it belongs to, and not what it may become. Score
only what the application itself enables: a multimodal capability counts only where that modality is
core to the ability. Weigh how far the ability's tasks decompose into codifiable steps, what inputs
and outputs are involved, how much the ability depends on context, physical presence or social
judgement, and how the application fails.

The reference scores in the calibration block are expert human judgements from Felten, Raj and
Seamans (2018) for this same application. Use them to fix where this application sits on the scale;
do not treat them as a ceiling or a floor for the ability you are asked about now."""


# ------------------------------- prompt assembly -------------------------------

def _anchor_block(anchors: pd.DataFrame, app_id: int, replicate: int) -> str:
    """The calibration exemplars shown for one application in one replicate.

    Each replicate rotates the anchor list by its own index, so replicate 0 shows anchors 0-4,
    replicate 1 shows 1-5, and so on. Different replicates therefore calibrate on different but
    equally valid exemplars drawn from the same FRS row, which is what makes the spread across
    replicates informative rather than decorative.
    """
    lines = []
    for label in ("high", "low"):
        sub = anchors[(anchors.ai_app_id == app_id) & (anchors.label == label)]
        items = sub.note.tolist()
        if not items:
            raise ValueError(f"application {app_id} has no {label} anchors; run build_anchors_v2.py")
        rot = items[replicate % len(items):] + items[: replicate % len(items)]
        lines += [f"  - {s}" for s in rot[:SHOW_ANCHORS]]
        if label == "high":
            lines.append("")
    return "\n".join(lines)


def build_system(app: pd.Series, anchors: pd.DataFrame, replicate: int) -> list[dict]:
    """System blocks: rubric, then the application and its calibration exemplars.

    Ordered stable-to-volatile because caching is a prefix match. The rubric is identical across all
    696 calls; the application block is identical across that application's 58 calls. The ability
    being scored is the only thing that varies per call, so it goes in the user turn, after the last
    cache breakpoint.
    """
    app_block = (
        f"AI APPLICATION\n"
        f"name: {app['name']}\n"
        f"definition: {app['short_definition']}\n\n"
        f"CALIBRATION (expert scores for this same application, Felten, Raj and Seamans 2018)\n"
        f"{_anchor_block(anchors, int(app['ai_app_id']), replicate)}"
    )
    return [
        {"type": "text", "text": RUBRIC},
        {"type": "text", "text": app_block, "cache_control": {"type": "ephemeral", "ttl": "1h"}},
    ]


def build_user(ability: pd.Series) -> str:
    return (
        f"HUMAN ABILITY\n"
        f"name: {ability['ability_name']}\n"
        f"definition: {ability['ability_definition']}\n\n"
        f"Score this application against this ability."
    )


def sample_cells(apps, abilities, per_app: int, seed: int) -> set[tuple[int, int]]:
    """A stratified sample of scoreable cells, for calibration sweeps.

    Restricted to FRS-covered abilities (1-52) and to cells that are *not* anchored, because the
    point of a sweep is to compare settings on held-out agreement with FRS, and an anchored cell
    cannot discriminate between settings: every setting is told the answer. Stratified by
    application so a sweep never compares one setting on vision against another on language.
    """
    held = pd.read_csv(MOD / "anchor_cells_v2.csv")
    anchored = set(map(tuple, held[["ai_app_id", "ability_id"]].astype(int).values))
    eligible = [int(a) for a in abilities.ability_id if int(a) <= 52]
    rng = np.random.default_rng(seed)
    picked: set[tuple[int, int]] = set()
    for app_id in apps.ai_app_id.astype(int):
        pool = [b for b in eligible if (app_id, b) not in anchored]
        take = rng.choice(pool, size=min(per_app, len(pool)), replace=False)
        picked |= {(app_id, int(b)) for b in take}
    return picked


def build_requests(apps, abilities, anchors, replicates: int, effort: str, max_tokens: int,
                   limit: int = 0, sample: set[tuple[int, int]] | None = None):
    """One request per (application, ability, replicate)."""
    reqs = []
    for replicate in range(replicates):
        for _, app in apps.iterrows():
            system = build_system(app, anchors, replicate)
            for _, ability in abilities.iterrows():
                if sample is not None and (int(app["ai_app_id"]), int(ability["ability_id"])) not in sample:
                    continue
                reqs.append({
                    "custom_id": f"a{int(app['ai_app_id'])}_b{int(ability['ability_id'])}_r{replicate}",
                    "params": {
                        "model": MODEL,
                        "max_tokens": max_tokens,
                        "system": system,
                        "messages": [{"role": "user", "content": build_user(ability)}],
                        "output_config": {"effort": effort, "format": {"type": "json_schema", "schema": SCORE_SCHEMA}},
                    },
                })
                if limit and len(reqs) >= limit:
                    return reqs
    return reqs


# ------------------------------- execution -------------------------------

def _client():
    """Build a client, bridging to the `ant` CLI profile when the SDK is too old to read it.

    Credential resolution is ANTHROPIC_API_KEY, then ANTHROPIC_AUTH_TOKEN, then an `ant auth login`
    profile. Recent SDKs walk that whole chain themselves; the version pinned here (0.91.0) stops
    after the two environment variables, so a machine authenticated only by `ant auth login` fails
    with "Could not resolve authentication method" even though a valid profile exists. Rather than
    upgrade the SDK underneath other code in this environment, fetch the profile's short-lived
    access token and pass it explicitly.

    OAuth access tokens are bearer tokens rather than API keys, so they go in `auth_token` and need
    the oauth beta header. They are short-lived and are not refreshed once handed over, which is why
    this is called per run rather than cached.
    """
    import subprocess

    import anthropic

    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return anthropic.Anthropic()

    try:
        token = subprocess.run(
            ["ant", "auth", "print-credentials", "--access-token"],
            capture_output=True, text=True, check=True, timeout=30,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise SystemExit(
            "No credential found. Set ANTHROPIC_API_KEY, or run `ant auth login`.\n"
            f"(tried the ant CLI and it failed: {exc})"
        ) from exc
    if not token:
        raise SystemExit("`ant auth print-credentials --access-token` returned nothing; try `ant auth login` again.")

    print("auth: using the ant profile's OAuth token (short-lived)", file=sys.stderr)
    return anthropic.Anthropic(
        auth_token=token,
        default_headers={"anthropic-beta": "oauth-2025-04-20"},
    )


def run_sync(reqs: list[dict], workers: int = 8) -> pd.DataFrame:
    """Score synchronously, a few at a time. For calibration sweeps, where a batch wait is the
    wrong trade.

    Modest concurrency rather than none: the cells are independent, and 240 sequential calls at
    high effort is most of an hour. Results are keyed by custom_id, so completion order is
    irrelevant. The SDK already retries 429 and 5xx with backoff, so no throttling here.
    """
    from concurrent.futures import ThreadPoolExecutor

    client = _client()

    def one(req: dict) -> dict:
        try:
            resp = client.messages.create(**req["params"])
            text = next(b.text for b in resp.content if b.type == "text")
            return _row(req["custom_id"], json.loads(text), resp.usage)
        except Exception as exc:                                   # noqa: BLE001
            return _row(req["custom_id"], None, None, error=str(exc))

    rows, done = [], 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for row in pool.map(one, reqs):
            rows.append(row)
            done += 1
            if done % 20 == 0 or done == len(reqs):
                print(f"  {done}/{len(reqs)}", file=sys.stderr)
    return pd.DataFrame(rows)


def submit_batch(reqs: list[dict]) -> str:
    client = _client()
    batch = client.messages.batches.create(requests=reqs)
    print(f"batch id: {batch.id}\nstatus:   {batch.processing_status}")
    (MOD / "last_batch_id.txt").write_text(batch.id)
    return batch.id


def collect_batch(batch_id: str) -> pd.DataFrame:
    """Gather batch results.

    Results arrive in arbitrary order, so everything is keyed by custom_id and never by position.
    """
    client = _client()
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        if batch.processing_status == "ended":
            break
        print(f"  {batch.processing_status}: {batch.request_counts}", file=sys.stderr)
        time.sleep(30)

    rows = []
    for res in client.messages.batches.results(batch_id):
        if res.result.type == "succeeded":
            msg = res.result.message
            text = next((b.text for b in msg.content if b.type == "text"), "")
            try:
                rows.append(_row(res.custom_id, json.loads(text), msg.usage))
            except json.JSONDecodeError as exc:
                rows.append(_row(res.custom_id, None, None, error=f"unparseable: {exc}"))
        else:
            err = getattr(res.result, "error", res.result.type)
            rows.append(_row(res.custom_id, None, None, error=str(err)))
    return pd.DataFrame(rows)


def _row(custom_id: str, parsed: dict | None, usage, error: str = "") -> dict:
    app_id, ability_id, replicate = (int(p[1:]) for p in custom_id.split("_"))
    row = {
        "ai_app_id": app_id, "ability_id": ability_id, "replicate": replicate,
        "r": np.nan, "rationale": "", "confidence": "", "error": error,
        "input_tokens": np.nan, "output_tokens": np.nan,
        "cache_read_tokens": np.nan, "cache_write_tokens": np.nan,
    }
    if parsed is not None:
        row["r"] = float(np.clip(float(parsed.get("r", np.nan)), 0.0, 1.0))
        row["rationale"] = str(parsed.get("rationale", ""))
        row["confidence"] = str(parsed.get("confidence", ""))
    if usage is not None:
        row["input_tokens"] = getattr(usage, "input_tokens", np.nan)
        row["output_tokens"] = getattr(usage, "output_tokens", np.nan)
        # input_tokens is the uncached remainder only; the prompt total is the sum of all three.
        row["cache_read_tokens"] = getattr(usage, "cache_read_input_tokens", np.nan)
        row["cache_write_tokens"] = getattr(usage, "cache_creation_input_tokens", np.nan)
    return row


# ------------------------------- aggregation -------------------------------

def aggregate(scores: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Median across replicates, plus the spread that median conceals.

    The median rather than the mean because it is robust to a single replicate going astray, which
    with three or more draws is the realistic failure mode. `r_range` is the headline uncertainty
    number: it is the width of the interval the calibration rotation moves the cell across.
    """
    ok = scores[scores.r.notna()]
    cell = ok.groupby(["ai_app_id", "ability_id"]).agg(
        r=("r", "median"), r_mean=("r", "mean"), r_sd=("r", "std"),
        r_min=("r", "min"), r_max=("r", "max"), n=("r", "size"),
    ).reset_index()
    cell["r_range"] = cell.r_max - cell.r_min
    matrix = cell.pivot(index="ai_app_id", columns="ability_id", values="r")
    return cell, matrix


# ------------------------------- cost -------------------------------

def estimate_cost(reqs: list[dict], batch: bool) -> dict:
    """Rough cost, from characters rather than the tokeniser, since counting needs the API.

    Deliberately conservative: assumes no cache hits and 4 characters per token. Output tokens are
    guessed, and on Opus 5 thinking is on by default and billed as output, so the output guess is
    where the real uncertainty sits. Treat this as an order of magnitude, not a quote.
    """
    in_price, out_price = 5.0 / 1e6, 25.0 / 1e6
    chars = 0
    for r in reqs:
        chars += sum(len(block["text"]) for block in r["params"]["system"])
        chars += len(r["params"]["messages"][0]["content"])
    in_tok = chars / 4.0
    out_tok = len(reqs) * 400          # short JSON plus adaptive thinking at moderate effort
    mult = 0.5 if batch else 1.0
    return {
        "requests": len(reqs),
        "est_input_tokens": int(in_tok),
        "est_output_tokens": int(out_tok),
        "est_usd_no_cache": round((in_tok * in_price + out_tok * out_price) * mult, 2),
        "est_usd_with_cache": round((in_tok * 0.2 * in_price + out_tok * out_price) * mult, 2),
        "note": "output tokens dominate; effort is the lever, not the prompt",
    }


# ------------------------------- main -------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apps", default=str(RAW / "applications_v2.csv"))
    ap.add_argument("--anchors", default=str(RAW / "anchors_v2.csv"))
    ap.add_argument("--replicates", type=int, default=3)
    ap.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--max-tokens", type=int, default=4000)
    ap.add_argument("--limit", type=int, default=0, help="cap requests, for dry runs")
    ap.add_argument("--sample", type=int, default=0,
                    help="stratified sample of N non-anchored cells per application, for sweeps")
    ap.add_argument("--seed", type=int, default=20260807, help="sample seed; keep fixed across a sweep")
    ap.add_argument("--tag", default=VANTAGE, help="suffix for output files")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--sync", action="store_true")
    g.add_argument("--submit", action="store_true")
    g.add_argument("--collect", metavar="BATCH_ID")
    args = ap.parse_args()

    apps = pd.read_csv(args.apps)
    abilities = pd.read_csv(RAW / "abilities.csv")
    anchors = pd.read_csv(args.anchors)

    if args.collect:
        scores = collect_batch(args.collect)
    else:
        sample = sample_cells(apps, abilities, args.sample, args.seed) if args.sample else None
        reqs = build_requests(apps, abilities, anchors, args.replicates, args.effort,
                              args.max_tokens, args.limit, sample)
        if args.dry_run:
            path = MOD / f"batch_requests_v{args.tag}.jsonl"
            with open(path, "w", encoding="utf-8") as fh:
                for r in reqs:
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            print(json.dumps(estimate_cost(reqs, batch=True), indent=2))
            print(f"\nwrote {path}")
            print("\n--- first request as it would be sent ---")
            first = reqs[0]["params"]
            for b in first["system"]:
                print(b["text"][:1400])
                print("  " + "." * 60)
            print(first["messages"][0]["content"])
            return
        if args.submit:
            submit_batch(reqs)
            return
        scores = run_sync(reqs)

    scores_path = MOD / f"mapping_scores_claude_v{args.tag}.csv"
    scores.to_csv(scores_path, index=False)

    cell, matrix = aggregate(scores)
    cell.to_csv(MOD / f"mapping_cells_claude_v{args.tag}.csv", index=False)
    matrix.to_csv(OUT / f"mapping_matrix_claude_v{args.tag}.csv")

    n_err = int(scores.error.astype(bool).sum())
    report = {
        "vantage": args.tag,
        "model": MODEL,
        "effort": args.effort,
        "replicates": args.replicates,
        "anchors_shown_per_direction": SHOW_ANCHORS,
        "applications": int(apps.ai_app_id.nunique()),
        "abilities": int(abilities.ability_id.nunique()),
        "requests": int(len(scores)),
        "errors": n_err,
        "cells": int(len(cell)),
        "median_replicate_range": float(cell.r_range.median()) if len(cell) else None,
        "cells_with_range_ge_0_25": int((cell.r_range >= 0.25).sum()) if len(cell) else None,
        "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (OUT / f"run_report_claude_v{args.tag}.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    if n_err:
        print(f"\nWARNING: {n_err} requests failed; see {scores_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
