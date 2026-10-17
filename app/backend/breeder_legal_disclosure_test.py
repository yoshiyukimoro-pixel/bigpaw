"""Fail-closed legal disclosure and unchanged visit flow regression gate."""
from pathlib import Path
import ast
import re
import sqlite3

ROOT=Path('/app')
s=(ROOT/'backend/server.py').read_text(encoding='utf-8')
compile(s,str(ROOT/'backend/server.py'),'exec')
allpages={name:(ROOT/name).read_text(encoding='utf-8') for name in
    ('breeder-register.html','breeder-profile-edit.html','breeder-detail.html','puppy-detail.html','breeders.html','messages.html','visit-confirm.html')}

for token in ('operatorName','officeName','officeAddress','businessType','registrationNo',
              'registrationDate','expiresOn','animalManager'):
    assert "'"+token+"':" in s or "'"+token+"' :" in s,('LEGAL_PUBLIC_OUTPUT_MISSING',token)

# Only approved, non-suspended, explicitly confirmed, fully populated breeders
# may return their exact registered business office location.
assert "not row['confirmed']" in s,'PUBLIC_CONSENT_GATE_MISSING'
assert "row['review_status']!='approved'" in s,'PUBLIC_APPROVAL_GATE_MISSING'
assert "row['billing_suspended']" in s,'PUBLIC_SUSPENSION_GATE_MISSING'
assert "not all(str(v or '').strip() for v in vals)" in s,'INCOMPLETE_LEGAL_FIELDS_GATE_MISSING'
assert 'if not data.get(' in s and 'confirmPublicDisclosure' in s,'EXPLICIT_BREEDER_CONSENT_MISSING'
assert "u=self.require(['breeder'])" in s,'LEGAL_EDITOR_AUTH_MISSING'
assert "legal_ad_consent" in s and "status=='approved'" in s,'OPERATOR_APPROVAL_LEGAL_INHERITANCE'
assert 'confirmed=0 WHERE breeder_id' in s,'RECONFIRM_AFTER_ADDRESS_CHANGE_MISSING'

# New signup does not duplicate the registered location or legal business ID.
signup=allpages['breeder-register.html']
assert 'id="visitAddress"' in signup,'SINGLE_REGISTERED_ADDRESS'
assert 'id="legalRegistrationDate"' in signup,'REGISTRATION_DATE'
assert 'id="legalAnimalManager"' in signup,'ANIMAL_MANAGER'
assert 'id="legalAdConsent"' in signup,'EXPLICIT_DISCLOSURE_NOTICE'
assert 'legalRegistrationDate:byId(' in signup and 'legalAdConsent:byId(' in signup,'SIGNUP_API_FIELDS'
profile=allpages['breeder-profile-edit.html']
assert 'id="legalOfficeAddress"' in profile,'REGISTERED_ADDRESS_READONLY'
assert 'id="legalPublicConfirm"' in profile,'RECONFIRM_EXPLICIT'
assert 'id="visitAddress"' in profile,'EXISTING_VISIT_ADDRESS_UNCHANGED'
for page,holder in (('breeder-detail.html','breederLegalDetails'),('puppy-detail.html','puppyLegalDetails')):
    html=allpages[page]
    assert 'id="'+holder+'"' in html,('NO_LEGAL_SECTION',page)
    assert '/breeders/' in html and '/legal' in html,('LEGAL_FETCH_MISSING',page)
    for label in ('事業所の所在地','動物取扱責任者の氏名'):
        assert label in html,('STATUTORY_LABEL_MISSING',page,label)
assert 'id="visitInfoAuto"' in allpages['messages.html'],'BUYER_AUTO_NOTICE_PRESERVED'
assert 'visitContact' in s and 'private_visit_mail' in s,'VISIT_CONFIRMATION_AUTO_DELIVERY_BROKEN'
assert 'public_area' in s and 'city_level_public_location' in s,'ONLY_CITY_PUBLIC_LISTING_LOST'

# Verify the disclosure table has a strict default of "not public."
stmt=re.search(r'CREATE TABLE IF NOT EXISTS breeder_legal_disclosures\(.*?\);',s,re.S)
assert stmt,'LEGAL_SCHEMA_MISSING'
con=sqlite3.connect(':memory:')
con.execute('PRAGMA foreign_keys=OFF')
con.execute(stmt.group(0))
r=con.execute('PRAGMA table_info(breeder_legal_disclosures)').fetchall()
cols={row[1]:row for row in r}
assert cols['confirmed'][4]=='0','LEGAL_OPT_IN_DEFAULT'
con.execute('INSERT INTO breeder_legal_disclosures (breeder_id,operator_name,registration_date,expires_on,animal_manager,business_type,confirmed,updated_at) VALUES(?,?,?,?,?,?,?,?)',('b_test','代表者','2024-01-01','2029-12-31','責任者','販売',1,1))
assert con.execute('SELECT confirmed FROM breeder_legal_disclosures WHERE breeder_id=?',('b_test',)).fetchone()[0]==1,'LEGAL_TABLE_PERSISTENCE'
con.close()
print('BREEDER_LEGAL_DISCLOSURE_GATE_OK|eight_statutory_fields|explicit_consent|approved_only|public_display_breeder_and_puppy|auto_visit_preserved|no_duplicate_address|existing_unconfirmed_safe',flush=True)
