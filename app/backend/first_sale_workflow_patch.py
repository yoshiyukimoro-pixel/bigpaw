"""Install workflow after existing build patches without touching photo code."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'backend/server.py'
s=p.read_text()
marker="if __name__=='__main__':"
insert="from first_sale_workflow import install as _install_first_sale_workflow\n_install_first_sale_workflow(globals())\n\n"
if insert not in s:
    assert s.count(marker)==1
    s=s.replace(marker,insert+marker,1)
# Independent of billing suspension, so clearing an unpaid invoice cannot lift compliance suspension.
s=s.replace('COALESCE(b.billing_suspended,0)=0)', 'COALESCE(b.billing_suspended,0)=0 AND COALESCE(b.compliance_suspended,0)=0)')
s=s.replace('COALESCE(billing_suspended,0)=0', 'COALESCE(billing_suspended,0)=0 AND COALESCE(compliance_suspended,0)=0')
s=s.replace('COALESCE(b.billing_suspended,0)=0 GROUP', 'COALESCE(b.billing_suspended,0)=0 AND COALESCE(b.compliance_suspended,0)=0 GROUP')
s=s.replace("if brs and brs['billing_suspended']:","if brs and (brs['billing_suspended'] or con.execute('SELECT compliance_suspended FROM breeders WHERE id=?',(p['breeder_id'],)).fetchone()['compliance_suspended']):")
p.write_text(s)
print('FIRST_SALE_WORKFLOW_INSTALLED|independent_benefit_history|buyer_confirmation|compliance_guard')
