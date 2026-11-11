import json
from pathlib import Path
import tempfile
import unittest

from gemma4_verified_context import (
    check_syntax, compress_log, diagnostic_lines, slice_source,
)
from gemma4_verified_context.__main__ import main


SOURCE="""import sys

@decorate
class X:
    @property
    def total(self):
        return 42

    def compute(self, a):
        return a * 2

class Y:
    def compute(self, a):
        return a + 1
"""


class SliceTests(unittest.TestCase):
    def test_full_qualname(self):
        out = slice_source(SOURCE, "X.compute")
        self.assertFalse(out.returned_full_source)
        self.assertIn("return a * 2", out.text)
        self.assertNotIn("return a + 1", out.text)
    def test_decorator_kept(self):
        out = slice_source(SOURCE, "X.total")
        self.assertTrue(out.text.startswith("    @property"))
    def test_class_decorator_kept(self):
        out = slice_source(SOURCE, "X")
        self.assertTrue(out.text.startswith("@decorate"))
    def test_other_class_qualname(self):
        out = slice_source(SOURCE, "Y.compute")
        self.assertIn("return a + 1", out.text)
    def test_no_symbol_fail_open(self):
        out = slice_source(SOURCE, "X.missing")
        self.assertTrue(out.returned_full_source)
        self.assertEqual(out.text,SOURCE)
        self.assertEqual(out.fallback_reason,"symbol_not_found")
    def test_unqualified_method_fail_open(self):
        out = slice_source(SOURCE, "compute")
        self.assertTrue(out.returned_full_source)
    def test_duplicated_method_fail_open(self):
        src="def a():\n    pass\ndef a():\n    pass\n"
        out=slice_source(src,"a")
        self.assertEqual(out.fallback_reason,"ambiguous_symbol")
    def test_invalid_python_fail_open(self):
        src="def bad(:\n"
        self.assertEqual(slice_source(src,"bad").text,src)
    def test_context_increases_lines(self):
        out=slice_source(SOURCE,"X.compute",context_lines=1)
        self.assertIn("def compute",out.text)
        self.assertLess(out.start_line, out.end_line)
    def test_context_rejects_negative(self):
        with self.assertRaises(ValueError):slice_source(SOURCE,"X",context_lines=-1)
    def test_context_rejects_bool(self):
        with self.assertRaises(ValueError):slice_source(SOURCE,"X",context_lines=True)
    def test_empty_source(self):
        out=slice_source("","a")
        self.assertTrue(out.returned_full_source)
        self.assertEqual(out.start_line,0)
    def test_metadata_no_source_text(self):
        self.assertNotIn("text",slice_source(SOURCE,"X").metadata())
    def test_unicode_identifier(self):
        s="def пример():\n    return 'ok'\n"
        self.assertFalse(slice_source(s,"пример").returned_full_source)


class SyntaxTests(unittest.TestCase):
    def test_valid(self):
        self.assertTrue(check_syntax("def f():\n    return 5\n").passed)
    def test_invalid(self):
        r=check_syntax("def f(:\n")
        self.assertFalse(r.passed)
        self.assertIsNotNone(r.line)
    def test_top_level_return(self):
        self.assertFalse(check_syntax("return 1\n").passed)
    def test_top_level_await(self):
        self.assertFalse(check_syntax("await f()\n").passed)
    def test_safe_does_not_execute(self):
        self.assertTrue(check_syntax("raise RuntimeError('must not run')").passed)
    def test_metadata(self):
        self.assertIsNone(check_syntax("pass").message)


class CompressorTests(unittest.TestCase):
    def test_empty(self):
        r=compress_log("")
        self.assertEqual(r.raw_bytes,0)
        self.assertEqual(r.byte_reduction_pct,0.0)
    def test_type_error(self):
        with self.assertRaises(TypeError):compress_log(None)
    def test_exception_group_fails_open(self):
        s="ExceptionGroup: two exceptions (2 sub-exceptions)\n"
        self.assertEqual(compress_log(s).text,s)
    def test_native_traceback_preserved(self):
        s="Traceback (most recent call last):\n  File \"a.py\", line 1\nValueError: x\n"
        self.assertEqual(compress_log(s).text,s)
    def test_multiset_counts(self):
        text="E AssertionError\nE AssertionError\nFAILED test_x\n"
        self.assertEqual(diagnostic_lines(text)["E AssertionError"],2)
    def test_unicode_is_byte_count(self):
        s="E UnicodeError: ошибка\n"
        r=compress_log(s)
        self.assertEqual(r.raw_bytes,len(s.encode("utf-8")))
    def test_no_expansion(self):
        s="hello\n"
        r=compress_log(s)
        self.assertLessEqual(r.output_bytes,r.raw_bytes)
    def test_preserve_marker_duplicates(self):
        s="E AssertionError\nE AssertionError\n"
        r=compress_log(s)
        self.assertEqual(diagnostic_lines(r.text)["E AssertionError"],2)
    def test_metadata_no_text(self):
        r=compress_log("hello")
        self.assertNotIn("text",r.metadata())


class CliTests(unittest.TestCase):
    def test_check_success(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"a.py";p.write_text("pass\n")
            self.assertEqual(main(["check",str(p)]),0)
    def test_check_fail(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"b.py";p.write_text("return 2\n")
            self.assertEqual(main(["check",str(p)]),1)
    def test_slice_unknown_exit(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"a.py";p.write_text("pass\n")
            self.assertEqual(main(["slice",str(p),"nonexistent"]),2)


if __name__=="__main__":
    unittest.main()
