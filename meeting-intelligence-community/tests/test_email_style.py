from meeting_intelligence.core.email_style import generate_email_body, validate_first_paragraph


def test_footer_date_omits_year():
    body = generate_email_body("Alex Example", "https://docs.example", "outreach copy and onboarding", "June 2, 2026")
    assert "June 9!" in body
    assert "June 9, 2026" not in body


def test_first_paragraph_blacklist_only_checks_today_paragraph():
    body = """
    <p>Hello Alex,</p>
    <p>Today we covered outreach copy and onboarding.</p>
    <p>This later paragraph says game changer but should not fail.</p>
    """
    errors, warnings = validate_first_paragraph(body)
    assert errors == []
    assert warnings == []


def test_bad_first_paragraph_fails():
    body = "<p>Today we covered the strategic pivot and next steps from the call.</p>"
    errors, _ = validate_first_paragraph(body)
    assert any("strategic pivot" in err for err in errors)
    assert any("next steps from the call" in err for err in errors)
