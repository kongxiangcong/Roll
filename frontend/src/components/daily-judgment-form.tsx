import {type FormEvent, useRef, useState} from 'react';
import {request} from '../api';

export type JudgmentTarget = {
  instrument: string;
  noteId: string;
  comparator?: string | null;
  threshold?: number | null;
  priceOnly?: boolean;
};

type ReportForNote = {
  report_id: string;
  inputs: {
    listing: {members: {instrument: string}[]};
    account: {fills?: {record_id: string; instrument: string; direction: string; quantity: string; price: string}[]};
  };
};

export function DailyJudgmentForm({
  report, target, initialInstrument, disabled = false, onSaved, onSavingChange,
}: {
  report: ReportForNote;
  target?: JudgmentTarget;
  initialInstrument?: string;
  disabled?: boolean;
  onSaved?: () => void;
  onSavingChange?: (saving: boolean) => void;
}) {
  const members = report.inputs.listing.members;
  const [instrument, setInstrument] = useState(target?.instrument ?? initialInstrument ?? members[0]?.instrument ?? '');
  const [thesis, setThesis] = useState('');
  const [invalidation, setInvalidation] = useState('');
  const [threshold, setThreshold] = useState(target?.threshold?.toString() ?? '');
  const [comparator, setComparator] = useState(target?.comparator ?? 'ABOVE');
  const [priceOnly, setPriceOnly] = useState(target?.priceOnly ?? false);
  const [outcome, setOutcome] = useState(target ? 'REVIEWED' : 'WATCH');
  const [due, setDue] = useState('');
  const [fill, setFill] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const saving = useRef(false);
  const retry = useRef<{signature: string; key: string} | null>(null);
  const fills = report.inputs.account.fills?.filter(item => item.instrument === instrument) ?? [];
  const fillRequired = outcome === 'ACTED';

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving.current || disabled || !instrument || !thesis.trim() || !invalidation.trim() || (fillRequired && !fill)) return;
    saving.current = true;
    setBusy(true);
    onSavingChange?.(true);
    setError('');
    setSaved(false);
    const payload = {
      report_id: report.report_id,
      instrument,
      thesis,
      invalidation,
      outcome,
      ...(threshold ? {comparator, threshold: Number(threshold), ...(priceOnly ? {price_only: true} : {})} : {}),
      ...(due ? {due_date: due} : {}),
      ...(target ? {parent_note_id: target.noteId} : {}),
      ...(fillRequired ? {fill_record_id: fill} : {}),
    };
    const signature = JSON.stringify(payload);
    if (retry.current?.signature !== signature) {
      retry.current = {signature, key: crypto.randomUUID()};
    }
    try {
      await request('/daily-reports/notes', {...payload, idempotency_key: retry.current.key});
      retry.current = null;
      setThesis('');
      setInvalidation('');
      setThreshold('');
      setPriceOnly(false);
      setDue('');
      setFill('');
      setSaved(true);
      onSaved?.();
    } catch (error) {
      setError(String(error));
    } finally {
      saving.current = false;
      setBusy(false);
      onSavingChange?.(false);
    }
  }

  return <details open={target ? true : undefined}>
    <summary>记录判断、未行动原因与后续复查</summary>
    <form className="daily-judgment-form" onSubmit={event => void save(event)}>
      <fieldset disabled={busy || disabled}>
        <legend>{target ? '记录本条判断的复查' : '记录新的判断'}</legend>
        <label>证券
          <select value={instrument} disabled={!!target} onChange={event => {setInstrument(event.target.value); setFill('');}}>
            {members.map(member => <option key={member.instrument}>{member.instrument}</option>)}
          </select>
        </label>
        {target && <p>复查原记录 <code>{target.noteId}</code></p>}
        <label>判断 / 本次复查结论
          <textarea required autoFocus={!!target} maxLength={2000} value={thesis} onChange={event => setThesis(event.target.value)}/>
        </label>
        <label>哪些事实会推翻判断 / 未行动原因
          <textarea required maxLength={2000} value={invalidation} onChange={event => setInvalidation(event.target.value)}/>
        </label>
        <label>记录类型
          <select value={outcome} onChange={event => setOutcome(event.target.value)}>
            <option value="WATCH">持续观察</option>
            <option value="NO_ACTION">未行动</option>
            <option value="ACTED">已实际成交</option>
            <option value="REVIEWED">已复查</option>
          </select>
        </label>
        {fillRequired && <label>关联已确认成交
          <select required value={fill} onChange={event => setFill(event.target.value)}>
            <option value="">选择已确认成交</option>
            {fills.map(item => <option key={item.record_id} value={item.record_id}>
              {item.direction} {item.quantity} @ {item.price}
            </option>)}
          </select>
        </label>}
        <label>价格条件方向
          <select value={comparator} onChange={event => setComparator(event.target.value)}>
            <option value="ABOVE">收盘价达到或高于</option>
            <option value="BELOW">收盘价达到或低于</option>
          </select>
        </label>
        <label>可选价格条件
          <input type="number" min="0" step="any" value={threshold} onChange={event => setThreshold(event.target.value)}/>
        </label>
        {threshold && Number(threshold) > 0 && <label className="daily-judgment-check">
          <input type="checkbox" checked={priceOnly} onChange={event => setPriceOnly(event.target.checked)}/>
          这条判断的推翻条件只需核对上述收盘价
        </label>}
        <label>可选复查日期
          <input type="date" value={due} onChange={event => setDue(event.target.value)}/>
        </label>
        <button type="submit" disabled={!instrument || !thesis.trim() || !invalidation.trim() || (fillRequired && !fill)}>
          保存判断记录
        </button>
      </fieldset>
      {error && <p role="alert">{error}</p>}
      {saved && <p role="status">判断记录已保存。生成新报告后可查看该记录。</p>}
    </form>
  </details>;
}
