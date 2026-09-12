from pathlib import Path
import re

p = Path('index.html')
s = p.read_text(encoding='utf-8')

# Remove the old document-level handlers which clear validation messages.
s = re.sub(
    r"document\.addEventListener\('input',e=>\{const w=e\.target\.closest\('\.customer'\);.*?\}\);document\.addEventListener\('change',e=>\{const w=e\.target\.closest\('\.customer'\);.*?\}\);",
    '', s, count=1, flags=re.S)

# The Area select previously called clearValidation() after our validation
# controller ran. Keep the selected-area bookkeeping, but never erase the
# current validation state here.
s = re.sub(
    r"loc\.addEventListener\('change',\(\)=>\{loc\.dataset\.selectedArea=loc\.value;clearValidation\(\)\}\);",
    "loc.addEventListener('change',()=>{loc.dataset.selectedArea=loc.value});",
    s, count=1
)

# Remove any previous copy of the controller.
s = re.sub(
    r"\n/\* Definitive validation retry controller \*/.*?\n\}\)\(\);\n",
    '', s, count=1, flags=re.S
)

patch = r'''
/* Definitive validation retry controller - final */
(function(){
  function getErrors(w){
    const errors=[];
    const name=w.querySelector('.customer-name');
    const loc=w.querySelector('.location');
    const pharm=w.querySelector('.pharm');
    const qtys=[...w.querySelectorAll('.qty')];
    const ns=w.querySelector('.nostock');
    const photo=w.querySelector('.photo');

    if(!(name?.value||'').trim()) errors.push('Pharmacy / Customer name is required');
    if(!(loc?.value||'').trim()) errors.push('Area is required');

    const pv=(pharm?.value||'').trim();
    if(!pv) errors.push('Pharmacist is required');
    else if(!/^[A-Za-z][A-Za-z .\'-]{1,99}$/.test(pv)) errors.push('Pharmacist name is invalid');

    let positive=0, bad=false;
    qtys.forEach(q=>{
      const raw=(q.value||'').trim();
      if(raw!==''&&!/^\d+$/.test(raw)) bad=true;
      const n=raw===''?0:Number(raw);
      if(Number.isFinite(n)&&n>0) positive+=n;
    });
    if(bad) errors.push('Quantity must be a whole number of 0 or more');

    const noStock=!!ns?.checked;
    if(positive<=0&&!noStock) errors.push('Enter at least one positive quantity or select No Stock');
    if(noStock&&positive>0) errors.push('No Stock cannot be selected when a positive quantity is entered');

    if(!w.dataset.attachment && !(photo?.files?.length)) errors.push('Photo is required');
    return errors;
  }

  function refresh(w){
    if(!w || w.dataset.validationAttempted!=='1' || w.dataset.saving==='1') return;
    const m=w.querySelector('.msg');
    if(!m) return;
    const errors=getErrors(w);
    m.textContent=errors.length
      ? 'Please complete the following before saving:\n'+errors.map(x=>'• '+x).join('\n')
      : '';
    m.className=errors.length?'msg small err':'msg small';

    const b=w.querySelector('.save');
    if(b){
      b.disabled=false;
      b.removeAttribute('disabled');
      b.removeAttribute('aria-busy');
    }
  }

  // Mark the row as being in validation-retry mode before saveVisit runs.
  document.addEventListener('click',function(e){
    const b=e.target.closest('.customer .save');
    if(b){
      const w=b.closest('.customer');
      if(w) w.dataset.validationAttempted='1';
    }
  },true);

  // Capture phase gives immediate feedback. The delayed bubble-phase refresh
  // runs LAST, so any older row-specific handler cannot erase the message.
  function scheduleRefresh(e){
    const w=e.target.closest('.customer');
    if(w&&w.dataset.validationAttempted==='1') setTimeout(()=>refresh(w),0);
  }
  document.addEventListener('input',scheduleRefresh,true);
  document.addEventListener('change',scheduleRefresh,true);
  document.addEventListener('input',scheduleRefresh,false);
  document.addEventListener('change',scheduleRefresh,false);

  // Recalculate after saveVisit's own validation has completed.
  document.addEventListener('click',function(e){
    const w=e.target.closest('.customer');
    if(w&&e.target.closest('.save')) setTimeout(()=>refresh(w),0);
  },false);

  // Expose a harmless debug hook so the page always has one authoritative
  // validation recalculation function.
  window.__refreshPriceChangeValidation=refresh;
})();
'''

if '</script>' not in s:
    raise SystemExit('index.html has no closing script tag')
s = s.replace('</script>', patch + '\n</script>', 1)
p.write_text(s, encoding='utf-8')
print('FINAL validation controller patched')
