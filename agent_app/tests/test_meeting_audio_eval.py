from deal_agent.services.meeting_audio_eval import keyword_recall, normalized_error_rate


def test_keyword_recall_counts_expected_keywords():
    assert keyword_recall("今天討論 Odoo demo 和 Telegram 錄音", ["Odoo", "Telegram"]) == 1.0
    assert keyword_recall("今天討論 Odoo demo", ["Odoo", "Telegram"]) == 0.5


def test_normalized_error_rate_handles_exact_match():
    assert normalized_error_rate("We approved launch", "We approved launch") == 0.0
