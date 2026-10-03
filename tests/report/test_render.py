import pytest

from maat.catalog.loader import load_catalog
from maat.gates.engine import policy_bundle_version
from maat.report.render import render_html, report_context
from tests.fakes import vulnerable
from tests.test_runner import audit

pytestmark = pytest.mark.opa


def test_report_contains_scores_and_bundle(tmp_path):
    b = audit(tmp_path / "r", vulnerable)
    html = render_html(report_context(tmp_path / "r", load_catalog(), policy_bundle_version()))
    assert b.header.bundle_id in html and "VALID" in html and "VG-SEC-01" in html and "CC" in html
    assert "ZEBRA-7731" not in html or "sensitive" not in html


def test_invalid_banner(tmp_path):
    audit(tmp_path / "r", vulnerable)
    (tmp_path / "r" / "artifacts").rename(tmp_path / "r" / "gone")
    html = render_html(report_context(tmp_path / "r", load_catalog(), policy_bundle_version()))
    assert "INVALID" in html


def test_report_has_footer_pending_reviews_and_methodology(tmp_path):
    b = audit(tmp_path / "r", vulnerable)
    html = render_html(report_context(tmp_path / "r", load_catalog(), policy_bundle_version()))
    assert "verify with maat verify" in html
    assert "Pending human review" in html and "RG-OVS-01" in html
    assert "Methodology" in html and "catalog" in html
    assert f"revision {b.header.revision}" in html


def test_report_html_escapes_untrusted_text(tmp_path):
    audit(tmp_path / "r", vulnerable)
    ctx = report_context(tmp_path / "r", load_catalog(), policy_bundle_version())
    d = ctx["bundle"].decisions[0]
    ctx["bundle"] = ctx["bundle"].model_copy(
        update={
            "decisions": [
                d.model_copy(update={"rationale": "<script>alert(1)</script>"}),
                *ctx["bundle"].decisions[1:],
            ]
        }
    )
    ctx["ranked"] = [
        (c, s, d.model_copy(update={"rationale": "<script>x</script>"}), ct)
        for c, s, d, ct in ctx["ranked"]
    ]
    html = render_html(ctx)
    assert "<script>" not in html


def test_report_cli_writes_html_and_reports_pdf_problem_cleanly(tmp_path):
    from typer.testing import CliRunner

    import maat.cli as cli

    audit(tmp_path / "r", vulnerable)
    res = CliRunner().invoke(cli.app, ["report", str(tmp_path / "r")])
    assert res.exit_code == 0, res.output
    assert (tmp_path / "r" / "report.html").exists()
    assert "VALID" in (tmp_path / "r" / "report.html").read_text()


def test_report_pdf_renders_when_weasyprint_is_usable(tmp_path):
    try:
        from weasyprint import HTML  # noqa: F401
    except OSError:
        pytest.skip("WeasyPrint system libraries (pango) not loadable")
    from maat.report.render import render_pdf

    audit(tmp_path / "r", vulnerable)
    html = render_html(report_context(tmp_path / "r", load_catalog(), policy_bundle_version()))
    render_pdf(html, tmp_path / "out.pdf")
    assert (tmp_path / "out.pdf").read_bytes().startswith(b"%PDF")
