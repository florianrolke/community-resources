from scripts.extraction import classify_report_source, extract_guest_names, is_likely_person_name
def test_report_source_detection():
    assert classify_report_source('Genspark Research Report\nSources:') == 'genspark'
    assert classify_report_source('Perplexity research\nCitations\nRelated questions') == 'perplexity'
def test_guest_title_extraction():
    assert extract_guest_names('Ep 42 - Alexis Rivas, Cover: Building Prefab Homes') == ['Alexis Rivas']
    assert extract_guest_names('How to invest in mobile home parks') == []
    assert extract_guest_names('We spoke with Tomasz Mostowski and Luther Klein about model risk') == ['Tomasz Mostowski']
def test_name_validation():
    assert is_likely_person_name('Jane Smith')
    assert not is_likely_person_name('Mobile Home Park')
    assert not is_likely_person_name('The Risk Management Association')
    assert not is_likely_person_name('AI Governance')
