"""Pure CPU contracts shared by dry-run, client, supervisor and tests."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIMARY = "qie2511_q5_2ref_1mp_40steps"
SECONDARY = "qie2511_q5_2ref_0p5mp_40steps"
MODEL_CLASSES = frozenset({"UNETLoader", "UnetLoaderGGUF", "UnetLoaderGGUFAdvanced",
                          "CLIPLoader", "DualCLIPLoader", "TripleCLIPLoader",
                          "CLIPLoaderGGUF", "DualCLIPLoaderGGUF", "TripleCLIPLoaderGGUF",
                          "VAELoader", "ModelSamplingAuraFlow", "CFGNorm"})
LOADER_CLASSES = MODEL_CLASSES - {"ModelSamplingAuraFlow", "CFGNorm"}
EXIT_FAILURE = 2
EXIT_CACHED_RESULT = 23


class InvalidRun(RuntimeError):
    pass


class CachedResult(InvalidRun):
    pass


def require(condition, reason):
    if not condition:
        raise InvalidRun(reason)


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def owned_pids(pid):
    """The launched PID plus its descendants. The ComfyUI Desktop venv python.exe is a launcher (uv trampoline)
    that starts the real interpreter as a child, so bootstrap/listener/client PIDs are descendants, not the PID itself."""
    import psutil
    return {pid} | {child.pid for child in psutil.Process(pid).children(recursive=True)}


def digest_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_new(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=True)
        stream.write("\n")


def nodes_of(graph, ids):
    return [{"node_id": i, "class_type": graph[i]["class_type"]} for i in sorted(ids)]


def link(value):
    return isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and type(value[1]) is int


def cache_policy(graph, roots):
    require(len(set(roots)) == 2, "exactly two distinct image roots required")
    require(all(i in graph and graph[i]["class_type"] == "LoadImage" for i in roots), "A/B must be LoadImage")
    children = {i: set() for i in graph}
    parents = {i: set() for i in graph}
    for i, node in graph.items():
        for value in node["inputs"].values():
            if link(value):
                require(value[0] in graph and value[1] >= 0, "dangling/invalid graph link")
                children[value[0]].add(i)
                parents[i].add(value[0])
    visited, active = set(), set()

    def visit(i):
        require(i not in active, "cyclic graph")
        if i in visited:
            return
        active.add(i)
        for p in parents[i]:
            visit(p)
        active.remove(i)
        visited.add(i)
    for i in graph:
        visit(i)
    closure, pending = set(roots), list(roots)
    while pending:
        for child in children[pending.pop()]:
            if child not in closure:
                closure.add(child)
                pending.append(child)
    allowed = set(graph) - closure
    unexpected = nodes_of(graph, {i for i in allowed if graph[i]["class_type"] not in MODEL_CLASSES})
    require(not unexpected, f"human decision required: classes outside A/B closure: {unexpected}")
    for klass in ("TextEncodeQwenImageEditPlus", "VAEEncode", "KSampler", "VAEDecode", "SaveImage"):
        found = {i for i in graph if graph[i]["class_type"] == klass}
        require(found and found <= closure, f"missing or cacheable image computation: {klass}")
    return {"must_reexecute": nodes_of(graph, closure), "allowed_cached": nodes_of(graph, allowed),
            "loader_nodes": nodes_of(graph, {i for i in graph if graph[i]["class_type"] in LOADER_CLASSES})}


def frozen(config=PRIMARY, smoke=False):
    manifest = read_json(HERE / "manifest.json")
    require(config in manifest["configurations"], "unknown configuration; no fallback")
    entry = manifest["configurations"][config]
    require(entry["enabled"], "conditional 20-step configuration is deferred; human review required")
    path = HERE / entry["workflow"]
    require(sha256(path) == entry["sha256"], "workflow freeze mismatch")
    graph = read_json(path)
    policy = cache_policy(graph, manifest["image_nodes"])
    if smoke:
        samplers = [n for n in graph.values() if n["class_type"] == "KSampler"]
        require(len(samplers) == 1, "exactly one sampler required")
        samplers[0]["inputs"]["steps"] = 1
    return manifest, graph, policy, entry["sha256"]


def render(graph, a, b, prefix):
    graph = copy.deepcopy(graph)
    substitutions = {"__A__": a, "__B__": b, "__OUTPUT__": prefix}
    for node in graph.values():
        for key, value in node["inputs"].items():
            if isinstance(value, str) and value in substitutions:
                node["inputs"][key] = substitutions[value]
    return graph


def execution_graph(graph):
    """ComfyUI attaches LoadImage IS_CHANGED fingerprints to the prompt in place."""
    result = copy.deepcopy(graph)
    for node in result.values():
        node.pop("is_changed", None)
    return result


def validate_history(record, prompt_id, graph, state, control=False):
    status = record.get("status", {})
    messages = status.get("messages")
    require(isinstance(messages, list) and messages, "missing status.messages")
    require(status.get("completed") is True and status.get("status_str") == "success", "server execution failed")
    events = {}
    for message in messages:
        require(isinstance(message, (list, tuple)) and len(message) == 2, "malformed status.messages")
        kind, data = message
        require(isinstance(data, dict) and data.get("prompt_id") == prompt_id, "message belongs to another prompt")
        events.setdefault(kind, []).append(data)
    for name in ("execution_start", "execution_cached", "execution_success"):
        require(len(events.get(name, [])) == 1, f"missing/duplicate {name}")
    require(not ({"execution_error", "execution_interrupted"} & events.keys()), "execution failed/interrupted")
    cached = events["execution_cached"][0].get("nodes")
    require(isinstance(cached, list) and all(isinstance(i, str) for i in cached), "invalid cached nodes")
    require(len(cached) == len(set(cached)) and set(cached) <= set(graph), "unknown/duplicate cached nodes")
    roots = [i for i, n in graph.items() if n["class_type"] == "LoadImage"]
    policy = cache_policy(graph, roots)
    result = {**policy, "execution_cached": nodes_of(graph, cached), "cached_nodes": sorted(cached),
              "cache_validation_verdict": "ok"}
    if control:
        samplers = {i for i, n in graph.items() if n["class_type"] == "KSampler"}
        require(samplers <= set(cached), "smoke positive control: sampler was not cached")
        result["cache_validation_verdict"] = "expected_cached_result_smoke_control"
    elif (state == "cold" and cached) or (state == "warm" and set(cached) & {n["node_id"] for n in policy["must_reexecute"]}):
        error = CachedResult("FAIL:cached_result")
        result["cache_validation_verdict"] = "FAIL:cached_result"
        error.evidence = result
        raise error
    start = events["execution_start"][0]["timestamp"]
    stop = events["execution_success"][0]["timestamp"]
    require(type(start) in (int, float) and type(stop) in (int, float) and stop >= start, "invalid server timestamps")
    result["server_execution_s"] = (stop - start) / 1000
    return result


def validate_measure(report, sidecar, label, state):
    require(report.get("label") == label and report.get("state") == state, "measure binding mismatch")
    require(report.get("exit_code") == 0 and report.get("deadline_hit") is False and report.get("verdict") == "ok", "measure failed/deadline")
    require(not report.get("kill_survivors"), "watchdog survivors")
    require(sidecar.get("run_id") == label and sidecar.get("state") == state and sidecar.get("verdict") == "ok", "sidecar binding/verdict mismatch")
    require(sidecar.get("cache_validation_verdict") == "ok", "cache validation missing")
    launched = report.get("child_pid")
    require(launched is not None and (sidecar.get("client_pid") == launched or launched in (sidecar.get("client_ancestor_pids") or [])),
            "measured process mismatch")


def warm_consistency(sidecars):
    sets = [s["cached_nodes"] for s in sidecars if s["state"] == "warm"]
    return {"warm_cached_sets": sets, "warm_cache_divergence": any(set(x) != set(sets[0]) for x in sets[1:]),
            "policy": "divergence is evidence for review, not an automatic run failure"}
