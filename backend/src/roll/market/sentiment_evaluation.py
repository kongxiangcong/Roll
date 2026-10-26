"""Offline evaluation: abstention is a missed labeled class, never discarded."""
from collections import Counter


def evaluate_confusion(confusion: dict[str, int]) -> dict:
    classes = ('POSITIVE', 'NEGATIVE', 'NEUTRAL', 'IRRELEVANT')
    cells = []
    for key, count in confusion.items():
        truth, prediction = key.split('->')
        if truth not in classes or prediction not in classes and not prediction.startswith('ABSTAIN_'):
            raise ValueError('UNKNOWN_SENTIMENT_EVALUATION_LABEL')
        if type(count) is not int or count < 0:
            raise ValueError('INVALID_SENTIMENT_EVALUATION_COUNT')
        cells.append((truth, prediction, count))
    support = Counter()
    predicted = Counter()
    correct = Counter()
    rejected = Counter()
    for truth, prediction, count in cells:
        support[truth] += count
        predicted[prediction] += count
        if truth == prediction:
            correct[truth] += count
        if prediction.startswith('ABSTAIN_'):
            rejected[truth] += count
    per_class = {}
    for label in classes:
        tp = correct[label]
        fn = support[label] - tp
        fp = predicted[label] - tp
        per_class[label] = {
            'support': support[label], 'tp': tp, 'fn': fn, 'fp': fp,
            'recall': tp / support[label] if support[label] else None,
            'precision': tp / predicted[label] if predicted[label] else None,
            'f1': 2 * tp / (2 * tp + fn + fp) if support[label] else None,
            'abstained': rejected[label],
        }
    binary = [per_class[label]['f1'] for label in ('POSITIVE', 'NEGATIVE')]
    return {
        'metric_scope': 'ALL_LABELED_ROWS_ABSTENTION_IS_FALSE_NEGATIVE',
        'per_class': per_class,
        'macro_f1': sum(binary) / 2 if all(value is not None for value in binary) else None,
        'positive_recall': per_class['POSITIVE']['recall'],
        'negative_recall': per_class['NEGATIVE']['recall'],
        'confusion': dict(confusion),
    }
