from basha.script.gender import guess_gender, split_gender_tag


def test_split_gender_tag_reads_explicit_tags():
    assert split_gender_tag("Ravi (male)") == ("Ravi", "male")
    assert split_gender_tag("Meena (female)") == ("Meena", "female")
    assert split_gender_tag("Arjun (M)") == ("Arjun", "male")
    assert split_gender_tag("Priya (f)") == ("Priya", "female")
    assert split_gender_tag("Narrator (male)") == ("Narrator", "male")


def test_split_gender_tag_without_tag():
    assert split_gender_tag("Ravi") == ("Ravi", None)
    assert split_gender_tag("Ravi (the king)") == ("Ravi (the king)", None)
    assert split_gender_tag(None) == (None, None)


def test_known_indian_names():
    assert guess_gender("Ravi") == "male"
    assert guess_gender("Arjun") == "male"
    assert guess_gender("Meena") == "female"
    assert guess_gender("Priya") == "female"


def test_known_western_names():
    assert guess_gender("John") == "male"
    assert guess_gender("Maria") == "female"


def test_uses_first_token_and_ignores_casing():
    assert guess_gender("ravi kumar") == "male"
    assert guess_gender("PRIYA") == "female"
    assert guess_gender("  Meena  ") == "female"


def test_unknown_and_non_name_speakers_return_none():
    # Non-name roles and ambiguous/unknown labels must not be guessed.
    assert guess_gender("Narrator") is None
    assert guess_gender("Guard") is None
    assert guess_gender("Zxqwlpp") is None
    assert guess_gender("") is None
    assert guess_gender(None) is None
