#!/usr/bin/env python3
from pathlib import Path

ROOT=Path('/app')
PAGE=ROOT/'puppy-detail.html'
html=PAGE.read_text(encoding='utf-8')

marker='<script id="bigpaw-public-puppy-description-guard">'
if marker in html:
    raise SystemExit('PUPPY_DESCRIPTION_GUARD_FAIL|duplicate_guard')
if '</body>' not in html:
    raise SystemExit('PUPPY_DESCRIPTION_GUARD_FAIL|body_close_missing')

script=r'''<script id="bigpaw-public-puppy-description-guard">
(()=>{
'use strict';
async function apply(){
  try{
    const id=new URLSearchParams(location.search).get('id');
    if(!id||!window.BigPawBridge)return;
    const p=await BigPawBridge.puppy(id);
    if(!p)return;
    const text=String(p.desc??p.description??p.comment??p.note??'').trim();
    let heading=[...document.querySelectorAll('h2')].find(h=>h.textContent.trim()==='この子について');
    let card=heading&&heading.closest('.card,section,article');
    let para=card&&card.querySelector('#desc,p');
    if(!card){
      const left=document.querySelector('section.section .grid.two > div');
      const first=left&&left.querySelector('.card');
      if(!left||!first)return;
      card=document.createElement('div');
      card.className='card pad';
      card.style.marginTop='18px';
      card.innerHTML='<h2>この子について</h2><p id="desc"></p>';
      first.insertAdjacentElement('afterend',card);
      para=card.querySelector('#desc');
    }
    if(!para){
      para=document.createElement('p');
      para.id='desc';
      card.appendChild(para);
    }
    para.textContent=text||'詳しい紹介文を掲載します。';
    para.style.setProperty('white-space','pre-wrap','important');
    para.style.setProperty('line-height','1.7','important');
  }catch(_e){}
}
function run(){apply();setTimeout(apply,250);setTimeout(apply,900)}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run,{once:true});else run();
window.addEventListener('pageshow',run);
})();
</script>'''

html=html.replace('</body>',script+'</body>',1)
if html.count(marker)!=1 or "p.desc??p.description" not in html or "この子について" not in html:
    raise SystemExit('PUPPY_DESCRIPTION_GUARD_FAIL|postcheck')
PAGE.write_text(html,encoding='utf-8')
print('PUPPY_DESCRIPTION_GUARD_OK|public_detail=preserved|source=desc|linebreaks=preserved|fallback=create_if_missing',flush=True)
