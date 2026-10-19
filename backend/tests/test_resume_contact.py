
from app.services.resume_contact import extract_contact


def test_contact_extraction():
    text = """
    Alex Morgan
    Email: alex@example.com
    Phone: +92 300 1234567
    """

    result = extract_contact(text)

    assert result.email == "alex@example.com"
    assert result.phone == "+92 300 1234567"


def test_missing_contact():
    result = extract_contact(
        "Software engineer experienced in backend systems"
    )

    assert result.email is None
    assert result.phone is None


def test_unlabeled_number_is_not_phone():
    result = extract_contact(
        "Completed 1234567890 transactions"
    )

    assert result.phone is None
