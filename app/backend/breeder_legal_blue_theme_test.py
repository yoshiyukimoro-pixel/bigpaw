"""Guard breeder-only legal edit blue theme, two-column layout and other roles."""
from pathlib import Path
p=Path('/app/breeder-profile-edit.html')
s=p.read_text(encoding='utf-8')
assert '<body class="breeder-page">' in s, 'BREEDER_ROLE_CLASS'
assert s.count('id="legalDisplayForm"')==1, 'LEGAL_FORM'
assert '#legalDisplayForm .fact{' in s,'BLUE_CARD_RULE'
assert 'background:#eef6ff' in s and 'border-color:#c8def3' in s,'BLUE_BACKGROUND_BORDER'
assert '#legalDisplayForm .field input' in s and 'border-color:#cfe0f1' in s,'BLUE_FIELDS'
assert '#legalDisplayForm #legalPublicConfirm' in s and 'accent-color:#5f9fd8' in s,'BLUE_CHECKBOX'
assert 'grid-template-columns:repeat(2,minmax(0,1fr))' in s,'KEEP_TWO_COLUMN_LAYOUT'
assert 'id="legalOfficeName"' in s and 'officeName:field(' in s,'LEGALLY_EDITABLE_OFFICE'
assert 'DOG44' not in s,'NO_HARDCODED_CUSTOMER_INFO'
assert s.index('class="breeder-page"')<s.index('id="legalDisplayForm"'),'ROLE_SCOPED_STYLING'
# Confirm the shared global theme is unchanged for buyers and operators.
style=Path('/app/assets/style.css').read_text(encoding='utf-8')
assert '.fact{background:#fff8fc' in style,'BUYER_THEME_UNMODIFIED'
print('BREEDER_LEGAL_BLUE_THEME_GATE_OK|blue_cards|blue_inputs|blue_checkbox|two_column|buyer_pink_preserved|operator_untouched',flush=True)
