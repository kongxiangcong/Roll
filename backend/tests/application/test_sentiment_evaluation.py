import pytest

from roll.market.sentiment_evaluation import evaluate_confusion


def test_abstention_stays_in_recall_denominator_and_other_classes_count_as_false_positives():
    result = evaluate_confusion({
        'POSITIVE->POSITIVE': 2, 'POSITIVE->ABSTAIN_LOW_CONFIDENCE': 2,
        'NEGATIVE->NEGATIVE': 1, 'NEGATIVE->POSITIVE': 1,
        'NEGATIVE->ABSTAIN_MARKET_INDEX': 2, 'NEUTRAL->POSITIVE': 1,
        'IRRELEVANT->ABSTAIN_RELEVANCE': 1,
    })
    assert result['positive_recall'] == 0.5
    assert result['negative_recall'] == 0.25
    assert result['per_class']['POSITIVE']['precision'] == 0.5
    assert result['per_class']['NEGATIVE']['fn'] == 3
    assert result['per_class']['NEUTRAL']['recall'] == 0
    assert result['per_class']['IRRELEVANT']['recall'] == 0
    assert result['macro_f1'] == pytest.approx((0.5 + 0.4) / 2)


def test_missing_class_is_unsupported_instead_of_perfect_or_zero_recall():
    result = evaluate_confusion({'POSITIVE->POSITIVE': 1})
    assert result['negative_recall'] is None
    assert result['macro_f1'] is None


@pytest.mark.parametrize('confusion', [{'OTHER->POSITIVE': 1}, {'POSITIVE->OTHER': 1}, {'POSITIVE->POSITIVE': -1}])
def test_invalid_evaluation_is_rejected(confusion):
    with pytest.raises(ValueError):
        evaluate_confusion(confusion)
