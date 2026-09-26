from fftf_tools.vocab import spoken_hits


def test_vocab_fence_word_boundaries():
    assert spoken_hits("The cartoon cut.")
    assert spoken_hits("A Cartoon title.")
    assert spoken_hits("The spine of the case.")
    assert spoken_hits("Call it Spine.")
    assert spoken_hits("cartoons") == []
    assert spoken_hits("cartoonish") == []
    assert spoken_hits("spines") == []


def test_vocab_fence_ignores_fence_section_and_preamble():
    text = """# Brief

Preamble mentions cartoon only as a file slug.

## Fiction

The public story was small.

## Fences

- Spoken narration must not contain the word cartoon.
- Spoken narration must not contain the word spine.
"""
    assert spoken_hits(text) == []


def test_vocab_fence_hits_spoken_section():
    text = "## COLD OPEN\n\nThis cartoon should fail.\n"
    hits = spoken_hits(text)
    assert len(hits) == 1
    assert hits[0]["word"].lower() == "cartoon"
    assert hits[0]["line"] == 3
