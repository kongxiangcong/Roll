from object_contract_candidate import project


def test_explicit_common_terminal_predicate_is_company_object():
    assert project('江西铜业、中国黄金国际等多股跌超4%','')['text']=='江西铜业、中国黄金国际等多股跌超4%'
    assert project('紫金矿业、江西铜业股份、云南铜业走强','')['reject_reason'] is None


def test_different_predicates_and_separate_mapping_stay_rejected():
    assert project('江西铜业上涨3%、紫金矿业下跌2%','')['reject_reason']=='ABSTAIN_NO_COMPANY_OBJECT'
    assert project('江西铜业及紫金矿业分别上涨2%和3%','')['reject_reason']=='ABSTAIN_NO_COMPANY_OBJECT'


def test_constituent_list_does_not_borrow_fund_direction():
    assert project('基金净值下跌1%','重仓股包括江西铜业、云南铜业等持仓占比下降')['reject_reason']=='ABSTAIN_NO_COMPANY_OBJECT'


def test_separate_company_predicate_cannot_be_borrowed():
    assert project('江西铜业召开股东会，紫金矿业下跌4%','')['text']=='江西铜业召开股东会'


def test_negation_is_kept_and_no_sentiment_label_is_generated():
    result=project('江西铜业公告未发生停产','')
    assert result['text']=='江西铜业公告未发生停产'
    assert 'label' not in result
