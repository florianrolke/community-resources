from scripts.score_podcast_opportunities import is_real_episode_url, score_row


def test_model_risk_opportunity_scores_high():
    row = {"episode_title": "Model Risk Management in the Age of AI and ML", "podcast_or_series": "Risk Podcast", "guest_or_speaker": "Jane Smith"}
    scored = score_row(row)
    assert scored["fit_tier"] == "high"
    assert "model risk" in scored["detected_themes"]


def test_personal_financial_engineering_is_penalized():
    row = {"episode_title": "Personal Financial Engineering w/ Davin Sessa", "podcast_or_series": "Personal Finance Podcast"}
    scored = score_row(row)
    assert scored["fit_tier"] == "low"


def test_google_search_urls_are_not_real_episode_urls():
    assert not is_real_episode_url({"episode_url": "http://www.google.com/search?q=model+risk+podcast"})
    assert is_real_episode_url({"episode_url": "https://podcasts.apple.com/us/podcast/example/id123"})
