import logging

from ephew.security import (
    REDACTION_PLACEHOLDER,
    CredentialRedactionFilter,
    install_redaction,
)

FAKE_KEY = "sk-ant-fake-DO-NOT-LOG-EVER"


def _capture(msg, *args, logger_name="test.security"):
    records: list[logging.LogRecord] = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record)

    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    handler = Capture()
    handler.setLevel(logging.DEBUG)
    handler.addFilter(CredentialRedactionFilter())
    logger.addHandler(handler)
    try:
        logger.info(msg, *args)
    finally:
        logger.removeHandler(handler)
    return [rec.getMessage() for rec in records]


def test_redacts_x_api_key_header_in_message():
    rendered = _capture(f"incoming x-api-key: {FAKE_KEY}")[0]
    assert FAKE_KEY not in rendered
    assert REDACTION_PLACEHOLDER in rendered


def test_redacts_authorization_bearer():
    rendered = _capture(f"Authorization: Bearer {FAKE_KEY}")[0]
    assert FAKE_KEY not in rendered
    assert REDACTION_PLACEHOLDER in rendered


def test_case_insensitive_variants():
    for header in ("X-API-KEY", "AUTHORIZATION", "authorization", "Proxy-Authorization"):
        rendered = _capture(f"{header}: {FAKE_KEY}")[0]
        assert FAKE_KEY not in rendered, f"leak for header {header}"


def test_redacts_header_dict_arg():
    rendered = _capture(
        "headers=%s",
        {"x-api-key": FAKE_KEY, "host": "api.anthropic.com"},
    )[0]
    assert FAKE_KEY not in rendered


def test_plain_message_unchanged():
    rendered = _capture("hello world")[0]
    assert rendered == "hello world"


def test_install_redaction_idempotent():
    root = logging.getLogger()
    before = sum(1 for f in root.filters if isinstance(f, CredentialRedactionFilter))
    install_redaction()
    install_redaction()
    after = sum(1 for f in root.filters if isinstance(f, CredentialRedactionFilter))
    assert after - before <= 1
