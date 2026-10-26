import pytest
from cninfo_materials import parse_rows


def test_whitespace_locator_keeps_raw_field_and_checks_identity():
    row = {'secCode':'600362','orgId':'gssh0600362','secName':'江西铜业','adjunctUrl':'finalpage/2013-01-30/62083230.PDF ',
           'announcementId':'62083230','announcementTitle':'关于整改的公告'}
    value = parse_rows([row],1,'METHOD')[0]
    assert value['source_path_reported'].endswith(' ')
    assert value['locator_whitespace_trimmed'] is True
    assert value['url'].endswith('/62083230.PDF')
    assert value['title']=='江西铜业：关于整改的公告'
    with pytest.raises(ValueError):
        parse_rows([{**row,'announcementId':'123'}],1,'METHOD')
    with pytest.raises(ValueError):
        parse_rows([{**row,'secCode':'OTHER'}],1,'METHOD')
