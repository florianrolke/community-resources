# Output Schemas

Podcast discovery columns: `podcast_name,niche,host_or_owner_name,company,website,youtube_url,rss_url,spotify_url,apple_url,linkedin_url,source,confidence,evidence`.

Guest/interviewee extraction columns: `podcast_name,episode_title,episode_url,platform,guest_name,guest_role,guest_company,linkedin_url,extraction_source,match_confidence,evidence`.

LinkedIn matchers append candidate review fields: `linkedin_candidate,linkedin_source,linkedin_confidence,linkedin_evidence_score,linkedin_notes,linkedin_candidates_json`.

Only auto-use `high` confidence matches. Keep `verify` rows for review.

The primary shareable deliverable for outreach is one row per interviewee/guest appearance, not only one row per podcast. Use `scripts/build_interviewee_linkedin_list.py` to combine YouTube channels, RSS feeds, and pasted Genspark/Perplexity episode reports into the guest/interviewee schema above.
