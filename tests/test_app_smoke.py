"""Run the whole Streamlit script headlessly on the sample data.

Catches what the unit tests can't: a renamed column, a Streamlit API change,
or an exception in a tab that only shows up when the page is built.
"""

from streamlit.testing.v1 import AppTest


def test_app_renders_sample_data_without_errors():
    at = AppTest.from_file("app.py", default_timeout=60).run()
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Sites monitored"] == "5"
    assert metrics["High-risk sites"] == "2"
