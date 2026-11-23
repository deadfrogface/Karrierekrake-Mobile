from core import cv_llm_runtime as rt
from scripts.ci_cv_import_exe_offline_e2e import llm_totals_delta


def test_totals_add_up_every_completion_including_model_load():
    before = rt.llm_totals()
    rt._publish_llm_step({"prompt_eval_s": 2.0, "gen_s": 3.0, "_load_s": 1.5})
    rt._publish_llm_step({"prompt_eval_s": 1.0, "gen_s": 0.5, "_load_s": 1.0})

    delta = llm_totals_delta(before, rt.llm_totals())

    assert delta == {"calls": 2, "load_s": 2.5, "prompt_eval_s": 3.0, "gen_s": 3.5}
    assert "_load_s" not in rt.last_llm_step_metrics()
