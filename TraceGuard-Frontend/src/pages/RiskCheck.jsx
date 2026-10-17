import { useState } from 'react';
import { ArrowDownRight, ArrowRight, CheckCheck, ChevronRight, CircleAlert, CircleCheck, Clock3, FlaskConical, Info, LoaderCircle, LockKeyhole, RotateCcw, ScanSearch, ShieldCheck, ShieldQuestion, Sparkles, Wallet, Workflow } from 'lucide-react';
import { useWorkspace } from '../context/WorkspaceContext';
import { recordTransaction, scoreTransaction } from '../services/api';
import { demoAssessment, DEMO_TRANSACTIONS, money, pct } from '../utils/data';
import { ActionPill, AlertMessage, Connection, RiskPill, SectionHeader, SourcePill, Surface } from '../components/Shared';

const initial = { transaction_id: 'TX-109368', sender_account_id: '4634', receiver_account_id: '18352', amount: '3.25', step: '121', sender_balance: '' };
const examples = [
  { name: 'High risk · report', id: 'TX-109368', sender: '4634', receiver: '18352', amount: '3.25', step: '121' },
  { name: 'Medium risk · report', id: 'TX-109389', sender: '8046', receiver: '9917', amount: '165.27', step: '121' },
  { name: 'Low risk · report', id: 'TX-109390', sender: '8050', receiver: '2878', amount: '196.13', step: '121' },
];
function getValidation(form) {
  const errors = {};
  for (const k of ['sender_account_id','receiver_account_id','step']) if (!/^\d+$/.test(String(form[k]).trim()) || !Number.isSafeInteger(Number(form[k]))) errors[k] = 'Enter a valid non-negative whole number.';
  if (!errors.sender_account_id && !errors.receiver_account_id && Number(form.sender_account_id) === Number(form.receiver_account_id)) errors.receiver_account_id = 'Choose a different receiving account.';
  if (!form.amount || !Number.isFinite(Number(form.amount)) || Number(form.amount) <= 0) errors.amount = 'Enter an amount greater than zero.';
  if (form.sender_balance && (!Number.isFinite(Number(form.sender_balance)) || Number(form.sender_balance) <= 0)) errors.sender_balance = 'Balance must be greater than zero.';
  return errors;
}
const fact = (label,val)=> <div className="result-fact"><span>{label}</span><strong>{val}</strong></div>;

export default function RiskCheck() {
  const { mode, health, addResult } = useWorkspace();
  const [form, setForm] = useState(initial);
  const [errors, setErrors] = useState({});
  const [result, setResult] = useState(null);
  const [source, setSource] = useState(null);
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState('');
  const [recorded, setRecorded] = useState(false);
  const [recording, setRecording] = useState(false);
  const update = (key,val) => { setForm(f=>({...f,[key]:val}));setErrors(e=>({...e,[key]:undefined})); };
  const choose = (e) => { setForm({ ...initial, transaction_id: e.id, sender_account_id: e.sender, receiver_account_id: e.receiver, amount: e.amount, step: e.step });setResult(null);setApiError('');setErrors({});setRecorded(false); };
  async function handleSubmit(e) {
    e.preventDefault();
    setApiError('');setResult(null);setRecorded(false);
    const errs = getValidation(form);setErrors(errs);
    if (Object.keys(errs).length) return;
    const req = { transaction_id: form.transaction_id.trim() || undefined,
      sender_account_id: Number(form.sender_account_id), receiver_account_id: Number(form.receiver_account_id),
      amount: Number(form.amount), step: Number(form.step), ...(form.sender_balance ? { sender_balance: Number(form.sender_balance) } : {}) };
    setLoading(true);
    try {
      if (mode === 'live') {
        const scored = await scoreTransaction(req);
        setResult(scored);setSource('live-api');addResult(req,scored,'live-api');
      } else {
        const offlineMatch = DEMO_TRANSACTIONS.find((t)=>t.transaction_id===req.transaction_id && t.sender_account_id===req.sender_account_id && t.receiver_account_id===req.receiver_account_id && t.amount===req.amount && t.step===req.step);
        const scored = offlineMatch ? { ...offlineMatch, sender_known: null, receiver_known: null, model_version: 'OFFLINE TEST REPORT', latency_ms: null } : demoAssessment(req);
        setResult(scored);const s=offlineMatch?'offline-report':'demo-rule';setSource(s);addResult(req,scored,s);
      }
    } catch(e) { setApiError(e.message); }
    finally { setLoading(false); }
  }
  return <>
    <SectionHeader eyebrow="INVESTIGATE / SCORING" title={<>Transaction <span className="heading-accent">risk check.</span></>} description="Screen a single transaction, review contextual indicators, and decide what deserves human attention." action={<span className="environment-badge"><span className={mode==='live'?'green-dot':'blue-dot'}/>{mode==='live'?'LIVE API MODE':'DEMO MODE'}</span>}/>
    <div className="riskcheck-grid"><div className="riskcheck-left">
      <div className="risk-banner"><div className="risk-banner-icon"><ScanSearch size={24}/></div><div><strong>Understand risk before the next step.</strong><p>Input an account pair and transfer details to receive a structured assessment.</p></div><span className="risk-banner-decoration">01 / 02</span></div>
      <Surface title="Transaction details" subtitle="Fields follow the exact ML scoring request format." aside={<span className="mini-tag">POST /score</span>}>
        <form className="risk-form" onSubmit={handleSubmit} noValidate>
          <div className="form-section-label">ACCOUNT INFORMATION</div>
          <div className="form-grid">
            <label className="form-field"><span>Sender account ID <i>*</i></span><div className={`input-wrap ${errors.sender_account_id?'invalid':''}`}><Wallet size={17}/><input type="text" inputMode="numeric" value={form.sender_account_id} onChange={e=>update('sender_account_id',e.target.value)} placeholder="e.g. 4634"/></div>{errors.sender_account_id&&<small className="field-error">{errors.sender_account_id}</small>}</label>
            <label className="form-field"><span>Receiver account ID <i>*</i></span><div className={`input-wrap ${errors.receiver_account_id?'invalid':''}`}><Wallet size={17}/><input type="text" inputMode="numeric" value={form.receiver_account_id} onChange={e=>update('receiver_account_id',e.target.value)} placeholder="e.g. 18352"/></div>{errors.receiver_account_id&&<small className="field-error">{errors.receiver_account_id}</small>}</label>
          </div>
          <div className="form-divider"/><div className="form-section-label">TRANSFER DETAILS</div>
          <div className="form-grid">
            <label className="form-field"><span>Transaction amount <i>*</i></span><div className={`input-wrap ${errors.amount?'invalid':''}`}><span className="input-prefix">$</span><input type="number" min="0.01" step="any" value={form.amount} onChange={e=>update('amount',e.target.value)} placeholder="0.00"/></div>{errors.amount&&<small className="field-error">{errors.amount}</small>}</label>
            <label className="form-field"><span>Transaction step <i>*</i></span><div className={`input-wrap ${errors.step?'invalid':''}`}><Clock3 size={17}/><input type="text" inputMode="numeric" value={form.step} onChange={e=>update('step',e.target.value)} placeholder="e.g. 121"/></div>{errors.step&&<small className="field-error">{errors.step}</small>}</label>
            <label className="form-field"><span>Transaction ID <small>(optional)</small></span><div className="input-wrap"><span className="input-symbol">#</span><input value={form.transaction_id} onChange={e=>update('transaction_id',e.target.value)} placeholder="TX-1001"/></div></label>
            <label className="form-field"><span>Sender balance <small>(optional)</small></span><div className={`input-wrap ${errors.sender_balance?'invalid':''}`}><span className="input-prefix">$</span><input type="number" min="0.01" step="any" value={form.sender_balance} onChange={e=>update('sender_balance',e.target.value)} placeholder="Leave blank"/></div>{errors.sender_balance&&<small className="field-error">{errors.sender_balance}</small>}</label>
          </div>
          <div className="form-info"><Info size={16}/><span>Use numeric AMLSim account IDs. Steps must not move backward in live mode. Scoring alone does not record or settle a transaction.</span></div>
          {apiError&&<AlertMessage type="error">{apiError}</AlertMessage>}
          <div className="form-actions"><button type="button" className="secondary-button" onClick={() => {setForm(initial);setErrors({});setResult(null);setApiError('');}}><RotateCcw size={15}/> Reset</button><button disabled={loading} type="submit" className="primary-button risk-submit">{loading?<LoaderCircle size={18} className="spin"/>:<ScanSearch size={18}/>} {loading?'Checking transaction...':'Check transaction risk'} <ArrowRight size={18}/></button></div>
        </form>
      </Surface>
      <div className="example-block"><div><span className="section-eyebrow">QUICK START</span><strong>Try a transaction from the test report</strong></div><div className="example-buttons">{examples.map(e=><button key={e.id} type="button" className="example-chip" onClick={()=>choose(e)}>{e.name}<ChevronRight size={14}/></button>)}</div></div>
    </div>
    <div className="riskcheck-right">
      <Surface className="assessment-panel" title="Risk assessment" subtitle="Result from the selected scoring source" aside={<span className="mini-tag">02 / 02</span>}>
        {!result ? <div className="waiting-result"><div className="waiting-graphic"><div className="waiting-circle"><ShieldQuestion size={43}/></div><div className="waiting-small a"/><div className="waiting-small b"/></div><h3>Ready for analysis</h3><p>Enter transaction details and run a risk check to see the score, recommended action, and available evidence.</p><span className="waiting-hint"><Sparkles size={15}/> Your assessment will appear here</span></div> : <div className="assessment-body"><div className="assessment-source"><SourcePill source={source}/><span>{source==='live-api' ? 'Model inference response' : source==='offline-report'?'Previously computed ML test result':'Illustrative rule-based calculation'}</span></div><div className={`risk-gauge ${result.risk_level.toLowerCase()}`} style={{ '--progress': `${Math.round(result.risk_score * 100)}%` }}><div className="risk-gauge-interior"><strong>{pct(result.risk_score)}</strong><span>RISK SCORE · 0–1</span></div></div><div className="assessment-status"><RiskPill level={result.risk_level}/><span>Suggested action</span><ActionPill action={result.recommended_action}/></div><div className="result-facts">{fact('Transaction ID',result.transaction_id||'Not supplied')}{fact('Model version',result.model_version)}{fact('Processing latency',result.latency_ms!=null?`${Number(result.latency_ms).toFixed(1)} ms`:'Not available')}{fact('Sender / receiver known',typeof result.sender_known==='boolean'?`${result.sender_known?'Yes':'No'} / ${result.receiver_known?'Yes':'No'}`:'Not available')}</div><div className="result-reasons"><h4>Risk indicators <span>{result.reasons.length}</span></h4>{result.reasons.length ? result.reasons.map((r,i)=><div className="reason-item" key={i}><strong>{r.code}</strong><span>{r.description}</span></div>) : <div className="no-reasons">No reason codes available for this result. This does not establish that the transfer is safe.</div>}</div><AlertMessage>{source==='live-api'?'Score is not a calibrated probability. Recommendations require analyst judgment.':source==='offline-report'?'This is a precomputed result from a synthetic test report; reasons were not exported.':'Placeholder demonstration only — not an AI prediction or validated fraud estimate.'}</AlertMessage>{source === 'live-api' && (<div style={{ marginTop: '0.85rem' }}><button type="button" disabled={recorded || recording} className="primary-button" style={{ width: '100%', justifyContent: 'center' }} onClick={async () => { setRecording(true); setApiError(''); try { await recordTransaction({ transaction_id: result.transaction_id, sender_account_id: Number(form.sender_account_id), receiver_account_id: Number(form.receiver_account_id), amount: Number(form.amount), step: Number(form.step), ...(form.sender_balance ? { sender_balance: Number(form.sender_balance) } : {}) }); setRecorded(true); } catch (err) { setApiError(err.message); } finally { setRecording(false); } }}>{recorded ? <CheckCheck size={16} /> : recording ? <LoaderCircle size={16} className="spin" /> : <Workflow size={16} />} {recorded ? 'Settled & Recorded in History' : recording ? 'Recording...' : 'Settle & Record in History (POST /record)'}</button></div>)}</div>}
      </Surface>
      <Surface className="connection-panel" title="Service readiness" subtitle="Connection information from /health"><div className="connection-row"><span>FastAPI backend</span><Connection/></div><div className="connection-row"><span>Trained model</span><Connection model/></div><p className="tiny-hint">Live inference is powered by tx_model.joblib, dynamic feature extraction, and the AMLSim HistoryStore.</p></Surface>
    </div></div>
  </>;
}
