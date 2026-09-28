from scripts.linkedin_matcher import clean_linkedin_url, score_candidate, slug_matches_name
def test_clean_linkedin_url():
    assert clean_linkedin_url('https://www.linkedin.com/in/jane-smith/?trk=x') == 'https://www.linkedin.com/in/jane-smith'
    assert clean_linkedin_url('https://www.linkedin.com/company/acme') == ''
def test_slug_matches_name():
    assert slug_matches_name('https://www.linkedin.com/in/jane-smith', 'Jane Smith')
    assert not slug_matches_name('https://www.linkedin.com/in/john-smith', 'Jane Smith')
def test_score_candidate_high():
    row={'host_or_owner_name':'Jane Smith','podcast_name':'Dental Growth Podcast','niche':'dental practice owners'}
    candidate={'url':'https://www.linkedin.com/in/jane-smith','title':'Jane Smith - Host of Dental Growth Podcast','content':'Dental practice owners and podcast host'}
    assert score_candidate(candidate,row)['confidence']=='high'
