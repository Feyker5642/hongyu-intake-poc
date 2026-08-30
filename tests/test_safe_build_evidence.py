import hashlib, importlib.util, json, subprocess, sys
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts/write_safe_build_evidence.py"
WORKFLOW = Path(__file__).parents[1] / ".github/workflows/safe-build.yml"
_spec = importlib.util.spec_from_file_location("safe_build_evidence", SCRIPT)
_module = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_module)
FILES = {"quest.yaml": b"q", "policy.yaml": b"p", "acceptance.yaml": b"a", "artifact-contract.yaml": b"c"}

def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)

def test_known_framing_digest(tmp_path):
    pack = tmp_path / "pack"; pack.mkdir()
    for name, data in FILES.items(): (pack / name).write_bytes(data)
    assert _module.pack_hash(pack) == "53a573714947391b2d4807d132f3ee276ee04d7362d80208bc99b46dc5cf184b"

def test_temporary_git_repo_produces_evidence(tmp_path):
    repo = tmp_path / "repo"; repo.mkdir(); pack = tmp_path / "pack"; pack.mkdir(); out = tmp_path / "evidence"
    for n, d in FILES.items(): (pack / n).write_bytes(d)
    def g(*x): subprocess.run(["git", "-C", str(repo), *x], check=True, stdout=subprocess.PIPE)
    g("init", "-q"); g("config", "user.email", "t@example.com"); g("config", "user.name", "Test")
    (repo / "file.txt").write_text("base\n"); g("add", "."); g("commit", "-qm", "base"); base = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    (repo / "file.txt").write_text("head\n"); g("commit", "-qam", "head"); head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    results = tmp_path / "pytest.txt"; results.write_bytes(b"5 passed\n")
    r = run("--build-pack", str(pack), "--repository", str(repo), "--base", base, "--head", head, "--test-results", str(results), "--output", str(out)); assert r.returncode == 0
    m = json.loads((out / "evidence-manifest.yaml").read_text()); assert m["baseCommit"] == base and m["headCommit"] == head
    assert m["buildPackHash"] == "53a573714947391b2d4807d132f3ee276ee04d7362d80208bc99b46dc5cf184b"
    assert len(m["artifacts"]) == 3 and m["artifacts"][2]["status"] == "passed"
    for x in m["artifacts"]: assert hashlib.sha256((out / x["path"]).read_bytes()).hexdigest() == x["sha256"]

def test_existing_output_is_not_touched(tmp_path):
    out = tmp_path / "existing"; out.mkdir(); sentinel = out / "sentinel"; sentinel.write_bytes(b"keep")
    r = run("--build-pack", str(tmp_path), "--repository", str(tmp_path), "--base", "x", "--head", "y", "--test-results", str(sentinel), "--output", str(out))
    assert r.returncode != 0 and sentinel.read_bytes() == b"keep"

def test_workflow_installs_only_trusted_base_requirements():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert 'git show "$BASE:requirements.txt" > "$RUNNER_TEMP/trusted-requirements.txt"' in workflow
    assert 'python -m pip install -r "$RUNNER_TEMP/trusted-requirements.txt"' in workflow
    assert "python -m pip install -r requirements.txt" not in workflow
    assert workflow.index("Run full deterministic tests") < workflow.index("Materialize trusted verification controls")
    assert "for f in quest.yaml policy.yaml acceptance.yaml artifact-contract.yaml; do" in workflow
    assert 'git show "$BASE:.safe-build/artwork-status-conflict/$f" > "$RUNNER_TEMP/trusted-build-pack/$f"' in workflow
    assert 'git show "$BASE:scripts/write_safe_build_evidence.py" > "$RUNNER_TEMP/write_safe_build_evidence.py"' in workflow
    assert "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1" in workflow
    assert "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97" in workflow
    assert "Feyker5642/safe-build-kit@2e6abe2bdf6ee31f4f2ca6ea84f0e367ca48090b" in workflow
    assert "persist-credentials: false" in workflow
