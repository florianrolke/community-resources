from scripts.generate_event_queries import generate_queries


def test_mhi_query_generation_contains_core_patterns():
    rows = generate_queries(
        niche="manufactured housing",
        city="Las Vegas",
        state="NV",
        year=2026,
        event_name="MHI 2026 Congress & Expo",
        companies=["EXO Edge"],
        people=["Nikki Greenberg|Futurist"],
        official_domains=["manufacturedhousing.org"],
    )
    queries = {r["query"] for r in rows}
    assert "manufactured housing conference 2026" in queries
    assert "site:manufacturedhousing.org annual meeting 2026" in queries
    assert "MHI 2026 Congress & Expo exhibitors 2026" in queries
    assert 'site:linkedin.com/in "Nikki Greenberg" "Futurist"' in queries
    assert 'site:linkedin.com/company "EXO Edge" LinkedIn' in queries


def test_local_suburb_generation():
    rows = generate_queries(niche="dental", city="Tijuana", state="BC", year=2026, suburbs=["Zona Rio", "San Diego"])
    queries = {r["query"] for r in rows}
    assert '"dental" events "Zona Rio"' in queries
    assert 'site:.org "dental" "San Diego" "events"' in queries


def test_association_level_generation_for_family_law():
    rows = generate_queries(
        niche="family law",
        city="Chicago",
        state="IL",
        year=2026,
        association_levels=["local", "regional", "national"],
    )
    queries = {r["query"] for r in rows}
    stages = {r["stage"] for r in rows}
    assert '"family law" "section" "Chicago" 2026' in queries
    assert '"Chicago" bar association "family law" events 2026' in queries
    assert '"family law" "state bar" "IL" 2026' in queries
    assert '"IL" "family law" association event calendar 2026' in queries
    assert '"family law" national "annual conference" 2026' in queries
    assert '"family law" "sponsors" United States 2026' in queries
    assert "local_association_discovery" in stages
    assert "regional_association_discovery" in stages
    assert "national_association_discovery" in stages
