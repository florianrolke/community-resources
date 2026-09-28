from scripts.common import read_csv
from scripts.find_linkedin_profiles import match_rows, normalize_linkedin_url, score_linkedin_match


def test_linkedin_match_confidence_examples():
    rows = match_rows(read_csv("tests/fixtures/mhi_contacts.csv"))
    by_name = {r["name"]: r for r in rows}
    assert by_name["Nikki Greenberg"]["match_confidence"] in {"confirmed", "probable"}
    assert by_name["EXO Edge"]["match_confidence"] == "confirmed"
    assert by_name["Thomas Casparian"]["match_confidence"] == "needs-manual-verification"


def test_linkedin_url_normalization():
    assert normalize_linkedin_url("https://mx.linkedin.com/in/test-person/?trk=x") == "https://www.linkedin.com/in/test-person"


def test_weak_profile_not_confirmed_from_url_alone():
    confidence, _ = score_linkedin_match("Thomas Casparian", "Cozen O'Connor", "person", "https://www.linkedin.com/in/someone-else", "Cozen O'Connor")
    assert confidence != "confirmed"