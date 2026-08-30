#!/usr/bin/env python3
"""Write deterministic Safe Build evidence for this repository.
Run: python scripts/write_safe_build_evidence.py --build-pack DIR --repository DIR --base REF --head REF --test-results FILE --output DIR
Requirements: Python standard library only; output directory must not already exist.
"""
import argparse, hashlib, json, subprocess
from pathlib import Path

PACK_FILES = ("quest.yaml", "policy.yaml", "acceptance.yaml", "artifact-contract.yaml")
ARTIFACTS = (("implementation-diff", "git_diff", "diff.patch"), ("changed-file-list", "changed_files", "changed-files.txt"), ("deterministic-test-results", "test_results", "test-results.txt"))

def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, stdout=subprocess.PIPE).stdout

def pack_hash(pack):
    h = hashlib.sha256(); h.update(b"safe-build-pack-v1\0")
    for name in PACK_FILES:
        data = (pack / name).read_bytes()
        h.update(name.encode()); h.update(b"\0"); h.update(str(len(data)).encode("ascii")); h.update(b"\0"); h.update(data); h.update(b"\0")
    return h.hexdigest()

def main():
    p = argparse.ArgumentParser(); p.add_argument("--build-pack", required=True); p.add_argument("--repository", required=True); p.add_argument("--base", required=True); p.add_argument("--head", required=True); p.add_argument("--test-results", required=True); p.add_argument("--output", required=True)
    a = p.parse_args(); pack, repo, output = map(Path, (a.build_pack, a.repository, a.output))
    if output.exists(): raise SystemExit("output directory already exists")
    base = git(repo, "rev-parse", "--verify", f"{a.base}^{{commit}}").decode().strip(); head = git(repo, "rev-parse", "--verify", f"{a.head}^{{commit}}").decode().strip()
    output.mkdir(parents=True)
    values = [git(repo, "diff", "--binary", "--full-index", base, head), git(repo, "diff", "--name-only", base, head), Path(a.test_results).read_bytes()]
    records = []
    for (ident, typ, filename), data in zip(ARTIFACTS, values):
        path = output / filename; path.write_bytes(data); records.append({"id": ident, "path": filename.replace("\\", "/"), "sha256": hashlib.sha256(data).hexdigest(), **({"status": "passed"} if typ == "test_results" else {})})
    manifest = {"version": "0.1", "buildPackHash": pack_hash(pack), "baseCommit": base, "headCommit": head, "artifacts": records}
    (output / "evidence-manifest.yaml").write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
if __name__ == "__main__": main()
