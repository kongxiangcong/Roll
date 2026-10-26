"""Identity-checked source projection; original metadata is always retained."""
import re
from object_contract import clean


def parse_rows(announcements, request, digest):
    result = []
    for ordinal,row in enumerate(announcements):
        if (row.get('secCode'),row.get('orgId'),row.get('secName'))!=('600362','gssh0600362','江西铜业'):
            raise ValueError('ISSUER_IDENTITY_MISMATCH')
        reported = row.get('adjunctUrl') or ''
        source_path = reported.strip()
        match = re.fullmatch(r'finalpage/(\d{4}-\d{2}-\d{2})/(\d+)\.PDF',source_path,re.I)
        if not match or match[2]!=str(row['announcementId']):
            raise ValueError('PDF_LOCATOR_IDENTITY_MISMATCH')
        original = clean(row['announcementTitle'])
        result.append({'id':'CNI-'+str(row['announcementId']),'request':request,'row':ordinal,'raw_sha256':digest,
                       'title':original if '江西铜业' in original else '江西铜业：'+original,'original_title':original,'summary':'','date':match[1],
                       'date_basis':'DISCLOSURE_PDF_PATH_DATE_NOT_HISTORICAL_PIT','url':'https://static.cninfo.com.cn/'+source_path,
                       'source_path_reported':reported,'locator_whitespace_trimmed':reported!=source_path,'media':'CNINFO issuer disclosure index',
                       'announcement_id':str(row['announcementId']),'reported_associate':row.get('associateAnnouncement')})
    return result
