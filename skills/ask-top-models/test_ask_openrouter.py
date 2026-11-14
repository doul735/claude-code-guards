"""Offline tests; all temporary files stay in this directory."""
import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from ask_openrouter import build_content, main

HERE = Path(__file__).resolve().parent


class OpenRouterTests(unittest.TestCase):
    def test_no_attachments_preserves_prompt(self):
        prompt = "원래 지시문\n\n"
        self.assertEqual(build_content(prompt, []), prompt)

    def test_two_attachments_in_order(self):
        self.assertEqual(
            build_content("지시문", [("./brief.md", "브리프 전문\n"),
                                     ("plan with spaces.md", "기획 전문")]),
            "지시문\n\n"
            "아래는 위에서 말한 파일의 내용이다. 너는 로컬 파일을 열 수 없으니 이 내용만으로 판단하라.\n"
            "[첨부 파일: ./brief.md]\n브리프 전문\n\n[첨부 끝]\n"
            "[첨부 파일: plan with spaces.md]\n기획 전문\n[첨부 끝]",
        )

    def test_missing_attachment_does_not_call_network(self):
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            prompt = Path(directory) / "prompt.md"
            prompt.write_text("지시문", encoding="utf-8")
            missing = str(Path(directory) / "missing.md")
            stderr = io.StringIO()
            with mock.patch.dict(os.environ, {
                "OPENROUTER_API_KEY": "fake-key",
                "OPENROUTER_MODEL": "fake-model",
            }), mock.patch("sys.argv", ["ask_openrouter.py", str(prompt), "--attach", missing]), \
                    mock.patch("urllib.request.urlopen") as urlopen, \
                    contextlib.redirect_stderr(stderr):
                self.assertEqual(main(), 2)
            urlopen.assert_not_called()
            self.assertEqual(stderr.getvalue(), f"첨부 파일을 못 읽었습니다: {missing}\n")


if __name__ == "__main__":
    unittest.main()
