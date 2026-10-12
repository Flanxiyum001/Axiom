"""Regression tests for PlannerAgent._normalize_code.

The Nebius/Nemotron provider double-escapes newlines and other escape
sequences in generated Python code (e.g. literal "\\n" instead of a real
newline), which made the validator reject otherwise-correct code.

The fix must:
- Unescape JSON-style escapes when the code is NOT valid Python.
- Leave valid Python untouched, so ordinary string contents, raw strings,
  regexes, and literal backslashes are never corrupted by a global
  unicode_escape decode.
"""

import ast

from axiom.agents.planner import _normalize_code


def _assert_parses(code: str) -> None:
    try:
        ast.parse(code)
    except SyntaxError as exc:  # pragma: no cover - diagnostic
        raise AssertionError(f"code does not parse: {exc}") from exc


def test_escaped_newlines_make_code_valid():
    """Code with literal \\n (not real newlines) fails to parse, then gets decoded."""
    # Simulate: the code has literal backslash-n sequences that prevent parsing.
    # The raw string uses \\\\n to represent a literal backslash-n in the Python source.
    raw = "import json\\nimport os\\nprint('hello')\\n"
    result = _normalize_code(raw)
    _assert_parses(result)
    assert "import json\n" in result
    assert "import os\n" in result


def test_escaped_unicode_quotes_are_decoded():
    """\\u0027 and \\u0022 become real quote characters when code fails to parse."""
    raw = "name = \\u0027axiom\\u0027\\nprint(name)\\n"
    result = _normalize_code(raw)
    assert "name = 'axiom'" in result
    _assert_parses(result)


def test_valid_code_with_string_newline_is_untouched():
    """A valid string literal containing \\n must NOT be decoded."""
    code = 'msg = "line1\\nline2"\nprint(msg)\n'
    result = _normalize_code(code)
    assert result == code
    assert 'msg = "line1\\nline2"' in result


def test_valid_code_with_raw_string_is_untouched():
    """Raw strings with backslashes (paths, regexes) must survive intact."""
    code = (
        "import re\n"
        'path = r"C:\\Users\\test\\file.txt"\n'
        'pattern = re.compile(r"\\d+\\.\\d+")\n'
        "print(path, pattern)\n"
    )
    result = _normalize_code(code)
    assert result == code
    assert 'r"C:\\Users\\test\\file.txt"' in result
    assert 'r"\\d+\\.\\d+"' in result


def test_valid_code_with_literal_backslashes_is_untouched():
    """Escaped backslashes in ordinary strings must not be collapsed."""
    code = 's = "C:\\\\Users\\\\axiom"\nprint(s)\n'
    result = _normalize_code(code)
    assert result == code
    assert 's = "C:\\\\Users\\\\axiom"' in result


def test_valid_code_with_regex_backslashes_is_untouched():
    """Non-raw regex strings with valid escapes must not be corrupted."""
    code = 'import re\np = re.compile("\\\\w+@\\\\w+")\nprint(p)\n'
    result = _normalize_code(code)
    assert result == code


def test_fully_escaped_realistic_script_is_decoded():
    """A realistic LLM payload (entire script on escaped newlines) becomes runnable."""
    raw = (
        "import json\\n"
        "import os\\n"
        "import time\\n"
        "MODE = os.environ.get('EXPERIMENT_MODE', 'baseline')\\n"
        "start = time.perf_counter()\\n"
        "acc = 0\\n"
        "for _ in range(1000):\\n"
        "    acc = (acc * 31 + 1) % 1000003\\n"
        "elapsed = (time.perf_counter() - start) * 1000.0\\n"
        "print(json.dumps({'metrics': [{'name': 'latency_ms', 'value': elapsed, 'unit': 'ms', 'iteration': 0}]}))\\n"
    )
    result = _normalize_code(raw)
    _assert_parses(result)
    assert "import json\n" in result
    assert "for _ in range(1000):\n" in result


def test_unparseable_code_falls_back_to_manual_replacement():
    """If unicode_escape produces garbage, targeted replacement is used."""
    raw = "def broken(:\\nprint('x')\\n"
    result = _normalize_code(raw)
    assert "\\n" not in result
    assert "print('x')" in result


def test_empty_and_plain_code_pass_through():
    assert _normalize_code("") == ""
    plain = "print('ok')\n"
    assert _normalize_code(plain) == plain