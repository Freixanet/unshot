"""Guard the domain rules that must stay in every prompt file."""

from pathlib import Path

import pytest

PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
FILES = ["api-system.md", "unshot-skill.md", "chatgpt-gpt.md"]
REQUIRED = [
    "85mm f/2.8", "50mm f/2.2",          # small / tabletop
    "50mm f/4", "35-50mm f/2.8",          # medium / standalone
    "24-35mm f/5.6-f/8", "1:1",           # large / architectural
    "sauna", "jacuzzi", "pedestal",
    "contact shadow", "refraction",
    "never invent",
]


@pytest.mark.parametrize("name", FILES)
def test_prompt_contains_domain_rules(name):
    text = (PROMPTS / name).read_text(encoding="utf-8").lower()
    missing = [r for r in REQUIRED if r.lower() not in text]
    assert not missing, f"{name} is missing: {missing}"


def test_gpt_instructions_forbid_printing_prompts():
    text = (PROMPTS / "chatgpt-gpt.md").read_text(encoding="utf-8").lower()
    assert "never print prompts" in text
