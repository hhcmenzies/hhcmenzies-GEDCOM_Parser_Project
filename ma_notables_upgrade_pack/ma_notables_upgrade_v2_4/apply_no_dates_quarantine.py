#!/usr/bin/env python3
"""
Post-process a run directory to quarantine records that have neither birth.year nor death.year.

Rule enforced:
  (birth.year is None) AND (death.year is None)  => quarantine

It rewrites in-place:
- master_ma_1600_1799.jsonl (filtered)
- collections/*.jsonl (filtered)

It also creates:
- rejected_no_dates.jsonl

If qa_report.json exists, it adds/updates:
- counts.rejected_no_dates
- counts.master_records_after_no_dates_filter

Usage:
  python apply_no_dates_quarantine.py out/runs/latest
"""
import argparse, json, os, glob

def has_any_year(o: dict) -> bool:
    b = (o.get("birth") or {}).get("year")
    d = (o.get("death") or {}).get("year")
    return (b is not None) or (d is not None)

def filter_jsonl(in_path: str, out_path: str, rej_fh):
    kept=0; rej=0
    with open(in_path, "r", encoding="utf-8") as fin, open(out_path, "w", encoding="utf-8") as fout:
        for line in fin:
            line=line.rstrip("\n")
            if not line:
                continue
            o=json.loads(line)
            if has_any_year(o):
                fout.write(json.dumps(o, ensure_ascii=False) + "\n")
                kept += 1
            else:
                rej_fh.write(json.dumps({**o, "reason":"missing_birth_and_death_year"}, ensure_ascii=False) + "\n")
                rej += 1
    return kept, rej

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("run_dir", help="Run dir (e.g., out/runs/latest or out/runs/2026-...Z)")
    args=ap.parse_args()
    root=args.run_dir

    master=os.path.join(root, "master_ma_1600_1799.jsonl")
    col_dir=os.path.join(root, "collections")
    qa_path=os.path.join(root, "qa_report.json")
    rej_path=os.path.join(root, "rejected_no_dates.jsonl")

    if not os.path.exists(master):
        raise SystemExit(f"Missing master: {master}")
    if not os.path.isdir(col_dir):
        raise SystemExit(f"Missing collections dir: {col_dir}")

    tmp_master=master+".tmp"
    tmp_map={}

    with open(rej_path, "w", encoding="utf-8") as rej_fh:
        kept_master, rej_master = filter_jsonl(master, tmp_master, rej_fh)

        for p in glob.glob(os.path.join(col_dir, "*.jsonl")):
            tmp=p+".tmp"
            filter_jsonl(p, tmp, rej_fh)
            tmp_map[p]=tmp

    os.replace(tmp_master, master)
    for p,tmp in tmp_map.items():
        os.replace(tmp, p)

    if os.path.exists(qa_path):
        try:
            qa=json.load(open(qa_path, "r", encoding="utf-8"))
            counts=qa.setdefault("counts", {})
            counts["rejected_no_dates"] = counts.get("rejected_no_dates", 0) + rej_master
            counts["master_records_after_no_dates_filter"] = kept_master
            with open(qa_path, "w", encoding="utf-8") as f:
                json.dump(qa, f, indent=2, ensure_ascii=False)
                f.write("\n")
        except Exception as e:
            print(f"WARNING: couldn't update qa_report.json: {e}")

    print("Applied no-dates quarantine")
    print("  master kept:", kept_master, "quarantined:", rej_master)
    print("  rejected_no_dates:", rej_path)

if __name__ == "__main__":
    main()
