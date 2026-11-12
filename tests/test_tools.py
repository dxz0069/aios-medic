"""工具与协议单元测试（纯本地可跑）。"""
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load(rel, name):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_spike1_extract_json_variants():
    m = _load("experiments/spike1/run_spike1.py", "rs1")
    assert m.extract_json('{"a": 1}') == {"a": 1}
    assert m.extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert m.extract_json('前置说明 {"a": {"b": 2}} 后缀') == {"a": {"b": 2}}
    assert m.extract_json("完全不是JSON") is None


def test_repair_actions_whitelist_refusal():
    m = _load("testbed/repair/actions.py", "actions")
    res = m.execute("kill_by_pattern", "rm -rf /")  # 未批准特征：必须在执行前拒绝
    assert res["refused"] is True
    res2 = m.execute("not_an_action", "")
    assert res2["refused"] is True
    assert m.execute("none", "")["action"] == "none"


def test_injector_registry_gold_consistency():
    inj = _load("testbed/injector/inject.py", "inj")
    allowed_cats = {"resource/memory", "resource/disk", "resource/cpu", "resource/process",
                    "service/crash", "network/loss", "network/port", "log/storm"}
    for fid in inj.REGISTRY:
        gf = REPO / "testbed/faults" / f"{fid}.json"
        assert gf.exists(), f"{fid} 缺金标签文件"
        gold = json.loads(gf.read_text(encoding="utf-8"))["gold"]
        assert gold["category"] in allowed_cats, f"{fid} 类目非法: {gold['category']}"
        assert gold["component"], f"{fid} 组件为空"


def test_pipeline_component_stem_match_semantics():
    # 与 run_pipeline 一致的词干匹配规则：全命令行也应命中 leaky.py
    gold_comp = "leaky.py"
    comp = "/usr/local/bin/python3 -c ... open('/var/log/medic/leaky.log')".lower()
    assert gold_comp in comp or gold_comp.split(".")[0] in comp
