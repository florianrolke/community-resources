from meeting_intelligence.vectorizer.chunking import chunk_text


def test_chunk_text_is_stable_and_overlaps():
    text = " ".join(f"word{i}" for i in range(100))
    chunks = chunk_text(text, words_per_chunk=30, overlap_words=5)
    assert len(chunks) == 4
    assert chunks[0]["word_start"] == 0
    assert chunks[1]["word_start"] == 25
    assert chunks[0]["content_hash"] == chunk_text(text, 30, 5)[0]["content_hash"]
