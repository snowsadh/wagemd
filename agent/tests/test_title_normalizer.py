"""Reject incomplete model classifications before ingesting DOL filings."""

import pytest

from src.normalization import title_normalizer


@pytest.mark.parametrize(
    "output,titles",
    [
        ("[]", ["Engineer"]),
        (
            ('[{"idx":0,"role_family":"SWE","level":"L3","confidence":0.9},'
             '{"idx":0,"role_family":"SWE","level":"L3","confidence":0.8}]'),
            ["Engineer", "Developer"],
        ),
        ('[{"idx":0,"role_family":"Unlisted","level":"L3","confidence":0.9}]', ["Engineer"]),
        ('[{"idx":0,"role_family":"SWE","level":"L3","confidence":1.5}]', ["Engineer"]),
    ],
)
def test_normalize_rows_rejects_incomplete_or_invalid_output(monkeypatch, output, titles):
    class FakeOpenAI:
        @staticmethod
        def user_content(prompt):
            return prompt

        @staticmethod
        def generate(**_):
            return None

        @staticmethod
        def text_of(_):
            return output

    monkeypatch.setattr(title_normalizer, "get_openai", FakeOpenAI)
    rows = [{"employer_normalized": "Example", "job_title_raw": title} for title in titles]
    with pytest.raises(ValueError, match="OpenAI returned"):
        title_normalizer.normalize_rows(rows)
