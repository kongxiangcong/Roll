from object_contract_candidate import project


def test_multi_company_keeps_only_target_predicate():
    value = project('甲公司利润增长，江西铜业利润下降', '')
    assert value['text']=='江西铜业利润下降'


def test_etf_genre_does_not_discard_explicit_company_object():
    value = project('某ETF市场观察', '江西铜业股价下跌，甲公司股价上涨')
    assert value['text']=='江西铜业股价下跌'


def test_neutral_is_not_rejected_for_missing_direction_cue():
    assert project('江西铜业召开股东大会', '')['reject_reason'] is None


def test_incidental_constituent_list_abstains():
    assert project('ETF持仓名单', '成分股包括江西铜业、甲公司等')['reject_reason']=='ABSTAIN_NO_COMPANY_OBJECT'


def test_shared_predicate_keeps_target():
    assert project('江西铜业、甲公司均下跌', '')['reject_reason'] is None


def test_ambiguous_per_company_mapping_abstains():
    assert project('江西铜业及甲公司分别上涨和下跌', '')['reject_reason']=='ABSTAIN_NO_COMPANY_OBJECT'


def test_negation_and_revision_preserved_without_sentiment_override():
    value = project('<em>江西铜业</em>更正公告：公司并未亏损', '')
    assert '并未亏损' in value['text'] and value['reject_reason'] is None
