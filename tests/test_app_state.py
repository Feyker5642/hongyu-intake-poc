"""Streamlit 狀態機測試：P0-4（案例載入）與 P0-5（確認後修改仍可匯出）。

用 Streamlit 內建的 AppTest，不需要瀏覽器。
"""
import pathlib

import pytest

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest  # noqa: E402

# AppTest 的相對路徑是相對於呼叫端檔案，所以一律給絕對路徑
APP = str(pathlib.Path(__file__).parent.parent / "app.py")


def boot():
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    return at


def test_demo_button_loads_case_text():
    """P0-4：按案例鈕，文字框必須立刻顯示該案例原文。"""
    at = boot()
    at.button(key="case_complete").click().run()
    assert "保養品彩盒" in at.session_state["text"]
    assert "保養品彩盒" in at.text_area[0].value


def test_second_case_replaces_first():
    at = boot()
    at.button(key="case_complete").click().run()
    at.button(key="case_sparse").click().run()
    assert "中秋禮盒" in at.text_area[0].value
    assert "保養品" not in at.text_area[0].value


def test_confirm_then_edit_revokes_confirmation():
    """P0-5：確認後改任何欄位，確認必須被撤銷、匯出必須重新鎖上。"""
    at = boot()
    at.button(key="case_complete").click().run()
    parse = [b for b in at.button if b.label == "解析需求"][0]
    parse.click().run()
    assert at.session_state["result"] is not None

    confirm = [b for b in at.button if b.label == "人工確認"][0]
    confirm.click().run()
    assert at.session_state["confirmed"] is True

    at.number_input(key="w_quantity").set_value(4000).run()
    assert at.session_state["confirmed"] is False, "改欄位後確認必須失效"
    assert "quantity" in at.session_state["edited"]


def test_edit_raw_text_invalidates_parse():
    """改原文之後不得用舊解析結果匯出。"""
    at = boot()
    at.button(key="case_complete").click().run()
    parse = [b for b in at.button if b.label == "解析需求"][0]
    parse.click().run()
    confirm = [b for b in at.button if b.label == "人工確認"][0]
    confirm.click().run()

    at.text_area[0].set_value("改成完全不同的需求 500 個紙盒").run()
    assert at.session_state["result"] is None, "原文變更必須作廢舊解析"
    assert at.session_state["confirmed"] is False
