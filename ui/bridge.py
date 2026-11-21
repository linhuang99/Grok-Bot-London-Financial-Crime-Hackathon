"""Standard-library bridge from a local UI to the existing screening runner.

The predictor receives input tables only. Labels are read exclusively by the
official validator when the user explicitly requests evaluation.
"""

import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
TABLE_KEYS = {
    "alerts": "alert_id", "hits": "hit_id", "customers": "record_id",
    "accounts": "account_id", "onboarding": "kyc_applicant_id",
    "kyc_checks": "check_id", "notes": "note_id", "search_results": "result_id",
}
INPUT_NAMES = tuple(name + ".jsonl" for name in TABLE_KEYS) + ("name_variants.json",)
OUTPUT_FIELDS = {"hit_id", "alert_id", "decision", "reason_code",
                 "customer_record_id", "reason", "evidence"}


def input_folder(folder):
    """Require a supplied input folder; never silently substitute another set."""
    folder = Path(folder).expanduser().resolve()
    for name in ("alerts.jsonl", "hits.jsonl"):
        if not (folder / name).is_file():
            raise ValueError("Missing required input: " + name)
    return folder


def fingerprint(folder):
    """Hash input and engine contents, not timestamps, labels or predictions."""
    folder = input_folder(folder)
    digest = hashlib.sha256()
    files = [("input/" + name, folder / name) for name in INPUT_NAMES]
    files += [("system/" + p.name, p) for p in sorted((ROOT / "system").iterdir())
              if p.is_file() and (p.suffix in (".py", ".json") or p.name == "run")]
    for label, path in files:
        digest.update(label.encode())
        if path.is_file():
            digest.update(b"\0present\0")
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        else:
            digest.update(b"\0missing\0")
    return digest.hexdigest()


def read_rows(path):
    rows = []
    with Path(path).open(encoding="utf-8-sig") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError("Expected JSON objects, one per line")
                rows.append(row)
    return rows


def prediction_text(predictions):
    return "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in predictions)


def validate_predictions(folder, predictions):
    """Check complete hit coverage and the bridge's official-output contract."""
    hits = read_rows(folder / "hits.jsonl")
    expected = {r["hit_id"]: r["alert_id"] for r in hits}
    seen = set()
    for row in predictions:
        if set(row) != OUTPUT_FIELDS:
            raise ValueError("Runner output fields do not match the official schema")
        key = row["hit_id"]
        if key in seen or key not in expected or row["alert_id"] != expected[key]:
            raise ValueError("Duplicate, unknown or incorrectly linked prediction")
        if row["decision"] not in {"SAME_ENTITY", "DIFFERENT_ENTITY", "REVIEW"}:
            raise ValueError("Unknown prediction decision")
        seen.add(key)
    if seen != set(expected):
        raise ValueError("Runner did not produce exactly one prediction per hit")


def run_screening(folder):
    """Call the team's runner in isolation; do not replace its decision rules."""
    folder = input_folder(folder)
    before = fingerprint(folder)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="screening-ui-") as temp:
        output = Path(temp) / "predictions.jsonl"
        process = subprocess.run(
            [sys.executable, str(ROOT / "system" / "run"), str(folder), str(output)],
            cwd=ROOT, capture_output=True, text=True, timeout=1800,
        )
        if process.returncode:
            raise ValueError("Screening runner failed: " + process.stderr[-4000:])
        predictions = read_rows(output)
        validator = ROOT / "validate.py"
        format_report = None
        if validator.is_file():
            checked = subprocess.run(
                [sys.executable, str(validator), "--data", str(folder), "--output", str(output)],
                cwd=ROOT, capture_output=True, text=True, timeout=180,
            )
            format_report = checked.stdout + checked.stderr
            if checked.returncode:
                raise ValueError("Official output validation failed: " + format_report[-4000:])
    validate_predictions(folder, predictions)
    if fingerprint(folder) != before:
        raise ValueError("Input or engine changed during this run; run again")
    alerts = read_rows(folder / "alerts.jsonl")
    decisions = {key: sum(row["decision"] == key for row in predictions)
                 for key in ("DIFFERENT_ENTITY", "SAME_ENTITY", "REVIEW")}
    grouped = {}
    for row in predictions:
        grouped.setdefault(row["alert_id"], []).append(row)
    cleared = [alert["alert_id"] for alert in alerts
               if alert.get("hit_ids") and all(
                   any(row["hit_id"] == hit and row["decision"] == "DIFFERENT_ENTITY"
                       for row in grouped.get(alert["alert_id"], []))
                   for hit in alert["hit_ids"])]
    return {"dataset": str(folder), "fingerprint": before,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "engine": "existing system/run; deterministic policy rules; no model calls",
            "predictions": predictions, "counts": decisions,
            "alerts": len(alerts), "cleared_alert_ids": cleared,
            "format_validation": format_report,
            "warnings": process.stderr.strip()}


def inspect_hit(folder, hit_id):
    """Return raw records and producer facts, with the original evidence IDs."""
    folder = input_folder(folder)
    before = fingerprint(folder)
    sys.path.insert(0, str(ROOT / "system"))
    import customer
    import data as data_module
    import hitfacts
    import link

    warnings = io.StringIO()
    with contextlib.redirect_stderr(warnings):
        data = data_module.load(str(folder))
        hit = data["hits_by_id"].get(hit_id)
        if not hit:
            raise ValueError("Hit not found in this dataset")
        alert = next((row for row in data["alerts"]
                      if row.get("alert_id") == hit.get("alert_id")), None)
        if alert is None:
            raise ValueError("The hit has no matching alert")
        issues = []
        try:
            groups = link.resolve(alert, data)
            persons = [customer.person(ids, data) for ids in groups]
        except Exception as exc:
            groups, persons = [], []
            issues.append("Customer facts unavailable: " + str(exc))
        try:
            facts = hitfacts.hit_facts(hit, data)
        except Exception as exc:
            facts = {}
            issues.append("Hit facts unavailable: " + str(exc))
    record_ids = {rid for group in groups for rid in group}
    records = [data["customers_by_id"][rid] for rid in sorted(record_ids)]
    emails = {data_module.text_key(row.get("email")) for row in records}
    accounts = [r for r in data["accounts"]
                if data_module.id_key(r.get("customer_id")) in record_ids]
    onboarding = [r for r in data["onboarding"]
                  if data_module.id_key(r.get("customer_id")) in record_ids]
    applicants = {data_module.id_key(r.get("kyc_applicant_id")) for r in onboarding}
    checks = [r for r in data["kyc_checks"]
              if data_module.id_key(r.get("applicant_id")) in applicants - {None}]
    notes = [r for r in data["notes"]
             if data_module.text_key(r.get("requester_email")) in emails - {None}]
    search_rows = []
    for name in facts.get("names", []):
        for row in data_module.find_search_results(data, name):
            if row not in search_rows:
                search_rows.append(row)
    related = {"alerts": [alert], "hits": [hit], "customers": records,
               "accounts": accounts, "onboarding": onboarding,
               "kyc_checks": checks, "notes": notes, "search_results": search_rows}
    evidence = {}
    for table, rows in related.items():
        for row in rows:
            key = row.get(TABLE_KEYS[table])
            if key:
                evidence.setdefault(key, []).append({"table": table, "record": row})
    if fingerprint(folder) != before:
        raise ValueError("Input or engine changed during inspection; run again")
    return {"alert": alert, "hit": hit, "persons": persons, "facts": facts,
            "related": related, "evidence_index": evidence,
            "warnings": [*data["warnings"], *issues],
            "fingerprint": before}


def evaluate(folder, predictions, labels):
    """Use the organisers' validator as the only scoring implementation."""
    folder = input_folder(folder)
    labels = Path(labels).expanduser().resolve()
    if not labels.is_file():
        raise ValueError("Labels file does not exist")
    validator = ROOT / "validate.py"
    if not validator.is_file():
        raise ValueError("Official local validate.py is missing")
    with tempfile.TemporaryDirectory(prefix="screening-score-") as temp:
        output = Path(temp) / "predictions.jsonl"
        output.write_text(prediction_text(predictions), encoding="utf-8")
        process = subprocess.run(
            [sys.executable, str(validator), "--data", str(folder),
             "--output", str(output), "--score", str(labels)],
            cwd=ROOT, capture_output=True, text=True, timeout=180,
        )
    report = process.stdout + process.stderr
    summary = re.search(r"(\d+) lines read, (\d+) problems", report)
    score = re.search(r"decision score ([\d.]+)", report)
    right = re.search(r"practice labels: (\d+) hits, (\d+) right decisions, (\d+) unsafe clearances", report)
    return {"exit_code": process.returncode, "report": report,
            "problems": int(summary[2]) if summary else None,
            "score": float(score[1]) if score else None,
            "labelled_hits": int(right[1]) if right else None,
            "correct": int(right[2]) if right else None,
            "unsafe_clearances": int(right[3]) if right else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("fingerprint", "run", "inspect", "evaluate"))
    parser.add_argument("data")
    parser.add_argument("--hit")
    parser.add_argument("--labels")
    args = parser.parse_args()
    try:
        if args.action == "fingerprint":
            result = {"fingerprint": fingerprint(args.data)}
        elif args.action == "run":
            result = run_screening(args.data)
        elif args.action == "inspect":
            result = inspect_hit(args.data, args.hit)
        else:
            if not args.labels:
                raise ValueError("Evaluation requires --labels")
            result = evaluate(args.data, json.load(sys.stdin), args.labels)
        print(json.dumps(result, ensure_ascii=False))
    except (ValueError, OSError, KeyError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
