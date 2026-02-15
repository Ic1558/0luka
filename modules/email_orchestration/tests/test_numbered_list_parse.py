from modules.email_orchestration.parse_command import extract_numbered_steps, parse_yaml_body


def test_extract_numbered_steps_dot_and_paren():
    text = "1. first\n2) second\n3. third"
    assert extract_numbered_steps(text) == ["first", "second", "third"]


def test_parse_yaml_body_falls_back_to_numbered_steps():
    body = "version: 1\nring: R2\n1. do thing\n2) do next"
    parsed = parse_yaml_body(body)
    assert parsed["ring"] == "R2"
    assert parsed["steps"] == ["do thing", "do next"]
