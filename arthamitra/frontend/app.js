/* No analytics, persistent document storage, external scripts or HTML injection. */
const $ = id => document.getElementById(id);
let selectedFile = null;
let limit = 5000000;
let pending = null;
const names = {loan_agreement:'Loan agreement',bank_passbook:'Bank passbook',government_scheme_letter:'Government scheme letter',repayment_schedule:'Repayment schedule',unknown:'Needs verification'};
function element(tag, text, className) { const el=document.createElement(tag); if(text!==undefined)el.textContent=text; if(className)el.className=className; return el; }
function choose(event) { selectedFile=event.target.files[0]||null; $('selected-file').textContent=selectedFile?selectedFile.name:'No document selected'; }
$('document').addEventListener('change',choose);
$('camera').addEventListener('change',choose);
function status(text,error=false){$('status').textContent=text;$('status').className=error?'error':'';}
function resetResults(){ $('results').hidden=true; $('empty-state').hidden=false; $('audio').pause(); $('audio').removeAttribute('src'); $('audio').load(); for(const id of ['fields','flags','steps','references','warnings','redacted-text','summary-kn','summary-en'])$(id).replaceChildren(); }
$('clear').addEventListener('click',()=>{resetResults();selectedFile=null;$('document').value='';$('camera').value='';$('consent').checked=false;$('selected-file').textContent='No document selected';status('Results cleared. Add another document when ready.');});
function render(data){
  $('empty-state').hidden=true;$('results').hidden=false;
  $('document-type').textContent=names[data.classification.document_type]||'Needs verification';
  $('explanation-mode').textContent=data.explanation.mode==='external_grounded'?'Grounded explanation · verify with the original':'Template explanation · external AI was not used successfully';
  $('summary-kn').textContent=data.explanation.summary.kn;$('summary-en').textContent=data.explanation.summary.en;
  const labels={principal:'Principal · INR',interest_rate:'Stated interest · %',tenure:'Tenure · months',instalment_amount:'Instalment · INR',fees:'Processing/upfront fee · INR',penalties:'Late charge · INR',insurance_charges:'Insurance · INR'};
  for(const [key,label] of Object.entries(labels)){const box=element('div',undefined,'field');box.append(element('dt',label),element('dd',data.fields[key]===null?'Not read':Number(data.fields[key]).toLocaleString('en-IN')));$('fields').append(box);}
  const basis=element('p',`Interest basis: ${data.fields.interest_basis}; period: ${data.fields.rate_period}.`,'subtle');$('flags').append(basis);
  if(!data.red_flags.length)$('flags').append(element('p','No configured rule was triggered. This is not confirmation that the document is safe.'));
  for(const flag of data.red_flags){const card=element('article',undefined,`flag ${flag.severity}`);const kn=element('p',flag.reason.kn);kn.lang='kn';card.append(element('span',`${flag.severity.toUpperCase()} · ${flag.rule_id}`,'flag-label'),kn,element('p',flag.reason.en),element('small',`Evidence: ${flag.evidence}`));$('flags').append(card);}
  for(const step of data.explanation.steps){const li=element('li');const kn=element('p',step.kn);kn.lang='kn';li.append(kn,element('p',step.en));$('steps').append(li);}
  for(const ref of data.rbi_citations){const li=element('li');const link=element('a',ref.title);const url=new URL(ref.url);if(url.protocol==='https:' && (url.hostname==='www.rbi.org.in'||url.hostname==='rbi.org.in')){link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';}li.append(link,element('p',`${ref.section} · ${ref.summary}`),element('p',`Scope: ${ref.scope} Checked: ${ref.verified_on}`));$('references').append(li);}
  if(!data.rbi_citations.length)$('references').append(element('li','No matching RBI reference was selected.'));
  for(const warning of data.warnings)$('warnings').append(element('li',warning));
  $('redacted-text').textContent=data.redacted_text;
  $('timing').textContent=`Server processing: ${(data.stage_timings_ms.total/1000).toFixed(2)} seconds. Excludes upload time.`;
  $('audio').hidden=data.audio.status!=='available';
  if(data.audio.status==='available' && data.audio.mime_type==='audio/mpeg'){$('audio').src=`data:audio/mpeg;base64,${data.audio.base64}`;$('audio-status').textContent='Listen in Kannada. Includes the advisory and next steps.';}else{$('audio-status').textContent=data.audio.message||'Audio unavailable. Read the Kannada text aloud.';}
}
$('analyze-form').addEventListener('submit',async event=>{
  event.preventDefault();if(!selectedFile){status('Choose a document first.',true);return;}if(selectedFile.size>limit){status('This document is too large. Please use a file under 5 MB.',true);return;}
  resetResults();$('analyze-button').disabled=true;status('Reading the document and preparing your explanation…');
  const form=new FormData();form.append('file',selectedFile);pending=new AbortController();const timer=setTimeout(()=>pending?.abort(),35000);
  try{const response=await fetch('/api/v1/analyze-document',{method:'POST',body:form,signal:pending.signal});const data=await response.json();if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'The document could not be processed.');render(data);status('Ready to review together. Check all amounts against the original.');}
  catch(error){status(error.name==='AbortError'?'The connection timed out. Try a smaller document.':error.message||'Connection failed. Please try again.',true);}
  finally{clearTimeout(timer);pending=null;$('analyze-button').disabled=false;}
});
fetch('/api/v1/health').then(r=>r.json()).then(data=>{limit=data.max_upload_bytes;$('mode').textContent=data.llm_mode==='offline'?'Local mode · no external LLM calls':'External LLM enabled · only verified facts are sent';}).catch(()=>{$('mode').textContent='Service not connected. Start the ArthaMitra backend.';});
