"""Keep breeder legal-information edit form in BIG PAW breeder blue theme.

Only modifies the authenticated breeder-profile-edit page. Public buyer pink
and operator yellow themes remain unchanged. Preserves the two-column cards.
"""
from pathlib import Path

PAGE=Path('/app/breeder-profile-edit.html')
html=PAGE.read_text(encoding='utf-8')
assert html.count('<body class="breeder-page">')==1,'BREEDER_PAGE_THEME_MISSING'
assert html.count('id="legalDisplayForm"')==1,'LEGAL_FORM_MISSING'
assert html.count('</style>')==1,'BREEDER_LOCAL_STYLE_MISSING'
assert html.count('id="legalOfficeName"')==1,'OFFICE_NAME_EDIT_FIELD_MISSING'

css="""
/* Legal-business editor belongs to the BREEDER (blue) workspace, not buyer pink. */
.breeder-page #legalDisplayForm .fact{
  background:#eef6ff;
  border-color:#c8def3;
  color:#354f6a;
  box-shadow:none;
  min-width:0;
  overflow-wrap:anywhere;
}
.breeder-page #legalDisplayForm .fact span,
.breeder-page #legalDisplayForm .fact label,
.breeder-page #legalDisplayForm .field label{
  color:#52708c;
}
.breeder-page #legalDisplayForm .fact b{color:#354f6a}
.breeder-page #legalDisplayForm .fact small,
.breeder-page #legalDisplayForm .muted{color:#5c7691}
.breeder-page #legalDisplayForm .fact input,
.breeder-page #legalDisplayForm .field input,
.breeder-page #legalDisplayForm .field select,
.breeder-page #legalDisplayForm .field textarea{
  min-width:0;
  max-width:100%;
  border-color:#cfe0f1;
  background:#fff;
  color:#354f6a;
}
.breeder-page #legalDisplayForm .fact input:focus,
.breeder-page #legalDisplayForm .field input:focus,
.breeder-page #legalDisplayForm .field select:focus,
.breeder-page #legalDisplayForm .field textarea:focus{
  border-color:#5f9fd8;
  outline:2px solid rgba(95,159,216,.18);
}
.breeder-page #legalDisplayForm #legalPublicConfirm{
  width:auto;
  accent-color:#5f9fd8;
}
.breeder-page #legalDisplayForm .fact-grid{
  grid-template-columns:repeat(2,minmax(0,1fr));
}
"""
html=html.replace('</style>',css+'</style>',1)
PAGE.write_text(html,encoding='utf-8')
print('BREEDER_LEGAL_BLUE_THEME_OK|legal_cards=blue|legal_inputs=blue|two_columns=preserved|public_theme=untouched|operator_theme=untouched',flush=True)
