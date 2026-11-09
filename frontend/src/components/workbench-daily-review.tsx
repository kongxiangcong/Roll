import {useEffect, useState} from 'react';
import {request} from '../api';
import {DailyJudgmentForm, type JudgmentTarget} from './daily-judgment-form';

type ReportVersion = {
  report_id: string;
  day: string;
  revision: number;
  known_by: string;
};

type SavedReport = ReportVersion & {
  inputs: {
    listing: {members: {instrument: string; identity: {name: string | null}}[]};
    account: {fills?: {record_id: string; instrument: string; direction: string; quantity: string; price: string}[]};
  };
};

type Judgment = {
  note_id: string;
  thesis: string;
  invalidation: string;
  state: string;
  price_state: 'TRIGGERED' | 'NOT_TRIGGERED' | 'UNKNOWN' | null;
  price_basis: {close: string | number | null; trade_date: string | null; available_at: string | null} | null;
  comparator: 'ABOVE' | 'BELOW' | null;
  threshold: number | null;
  due_date: string | null;
  due_triggered?: boolean;
  price_only?: boolean;
};

type HoldingReview = {
  instrument: string;
  weight_pct: number | null;
  status: 'REVIEW_REQUIRED' | 'INSUFFICIENT' | 'NO_NEW_REVIEW';
  impact: string;
  reasons: string[];
  changes: {kind: string; summary: string; references: string[]; status?: string}[];
  judgments: Judgment[];
};

type DailyReview = ReportVersion & {
  input_sha256: string;
  comparison: ReportVersion | null;
  account: {
    version: number;
    confirmed_at: string | null;
    cash_weight_pct: number | null;
    largest_weight_pct: number | null;
    constraints_status: string;
    constraints_reasons?: string[];
    funding_version?: number | null;
    valuation_as_of?: string | null;
  };
  holdings: HoldingReview[];
  exited_holdings?: {instrument: string; change: HoldingReview['changes'][number]}[];
};

const reviewStatus = {
  REVIEW_REQUIRED: '需要复查',
  INSUFFICIENT: '证据不足',
  NO_NEW_REVIEW: '暂无新增复查事项',
};
const judgmentStatus: Record<string, string> = {
  TRIGGERED: '价格条件已触发',
  NOT_TRIGGERED: '价格条件未触发',
  UNKNOWN: '价格条件待核对',
  DUE_FOR_REVIEW: '已到复查日期',
  MANUAL_REVIEW: '条件需人工核对',
};
const coverageStatus: Record<string, string> = {
  CHANGED: '有变化',
  UNCHANGED: '已核对范围内无变化',
  UNKNOWN: '证据不足',
  NO_BASELINE: '无比较基准',
};
const changeKind: Record<string, string> = {
  POSITION: '持仓',
  DAILY: '日线',
  FINANCIAL: '财务',
  NEWS: '新闻',
  ANNOUNCEMENT: '公告',
};
const constraintStatus: Record<string, string> = {
  UNKNOWN: '未知',
  WITHIN_BOUNDARY: '已核对约束未触发',
  BREACHED: '已触发约束',
  PAUSED: '已暂停',
};

function displayTime(value?: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN', {timeZone: 'Asia/Shanghai'}) : '未知';
}

function percent(value: number | null) {
  return value === null ? '未知' : `${value.toFixed(2)}%`;
}

function reportLabel(report: ReportVersion) {
  return `${report.day} · 第 ${report.revision} 版`;
}

function reportPath(reportId: string) {
  return '/daily-reports/' + encodeURIComponent(reportId);
}

function ReviewSections({
  review, report, onReview, saving,
}: {
  review: DailyReview;
  report: SavedReport;
  onReview: (target: JudgmentTarget) => void;
  saving: boolean;
}) {
  const {holdings, account, comparison} = review;
  const triggered = holdings.filter(holding => holding.judgments.some(judgment =>
    judgment.price_state === 'TRIGGERED' || judgment.state === 'TRIGGERED' || judgment.due_triggered,
  ));
  function holdingName(instrument: string) {
    const name = report.inputs.listing.members.find(member => member.instrument === instrument)?.identity?.name;
    return name ? `${name} · ${instrument}` : instrument;
  }

  return <>
    <p>当前报告 {reportLabel(review)} · 数据截止 {displayTime(review.known_by)}（北京时间）</p>
    <p>{comparison
      ? <>比较基准 {reportLabel(comparison)} · {comparison.day === review.day ? '同日更新' : '跨日比较'} · 数据截止 {displayTime(comparison.known_by)} · <a href={'/api' + reportPath(comparison.report_id)} target="_blank" rel="noreferrer">查看基准报告</a></>
      : '这份报告暂无比较基准。'}</p>
    <details>
      <summary>报告编号与冻结依据</summary>
      <p>报告编号 <code>{review.report_id}</code></p>
      <p>输入指纹 <code>{review.input_sha256}</code></p>
      <a href={'/api' + reportPath(review.report_id)} target="_blank" rel="noreferrer">查看本版冻结报告与证据</a>
    </details>
    <div className="cw-review-account">
      <p>报告账户版本 {account.version} · 确认于 {displayTime(account.confirmed_at)}</p>
      <p>现金占比 {percent(account.cash_weight_pct)} · 最大持仓占比 {percent(account.largest_weight_pct)}</p>
      <p>估值截至 {displayTime(account.valuation_as_of)}</p>
      <p>资金约束 {constraintStatus[account.constraints_status] ?? '未知'}{account.funding_version != null && ` · 授权版本 ${account.funding_version}`}</p>
      {account.constraints_reasons?.map(reason => <p key={reason}>{reason}</p>)}
    </div>
    {!!triggered.length && <p className="cw-note" role="status">
      复查提醒 · {triggered.map(holding => holdingName(holding.instrument)).join('、')} 已触发价格条件或到达复查日期。
    </p>}
    {!holdings.length && <p>本版报告没有持仓。</p>}
    {(holdings.length > 0 || !!review.exited_holdings?.length) &&
      <section className="cw-review-question">
        <h3>发生了什么变化</h3>
        {review.exited_holdings?.map(({instrument, change}) => <article key={instrument}>
          <h4>{holdingName(instrument)}</h4>
          <p>{change.summary}</p>
        </article>)}
        {holdings.map(holding => <article key={holding.instrument}>
          <h4>{holdingName(holding.instrument)}</h4>
          {holding.changes.length ? <ul>{holding.changes.map((change, index) => <li key={`${change.kind}-${index}`}>
            {changeKind[change.kind] && <strong>{changeKind[change.kind]} · </strong>}
            {change.status && coverageStatus[change.status] && <strong>{coverageStatus[change.status]} · </strong>}
            {change.summary}
            {!!change.references.length && <details>
              <summary>证据引用</summary>
              <ul>{change.references.map((reference, i) => <li key={i}><code>{reference}</code></li>)}</ul>
            </details>}
          </li>)}</ul> : <p>本版报告没有可比较的变化证据。</p>}
        </article>)}
      </section>}
    {holdings.length > 0 && <>
      <section className="cw-review-question">
        <h3>变化是否影响原持仓理由</h3>
        {holdings.map(holding => <article key={holding.instrument}>
          <h4>{holdingName(holding.instrument)}</h4>
          <p>{holding.impact}</p>
          {holding.judgments.length ? <ul>{holding.judgments.map(judgment => <li key={judgment.note_id}>
            <p>原持仓理由 · {judgment.thesis}</p>
            <p>推翻条件 · {judgment.invalidation}</p>
            <p>{judgmentStatus[judgment.price_state ?? judgment.state] ?? '待人工确认'}
              {judgment.due_triggered && judgment.price_state && ' · 已到复查日期'}
            </p>
            {judgment.price_basis?.close != null && <p>
              价格依据 {judgment.price_basis.trade_date ?? '日期未知'}收盘 {judgment.price_basis.close} 元 · 获知于 {displayTime(judgment.price_basis.available_at)}
            </p>}
            <button type="button" disabled={saving} onClick={() => onReview({
              instrument: holding.instrument,
              noteId: judgment.note_id,
              comparator: judgment.comparator,
              threshold: judgment.threshold,
              priceOnly: judgment.price_only,
            })}>记录本条复查</button>
          </li>)}</ul> : <p>缺少已记录的持仓理由，请在下方补记。</p>}
        </article>)}
      </section>
      <section className="cw-review-question">
        <h3>哪些持仓需要复查</h3>
        {holdings.map(holding => <article key={holding.instrument}>
          <h4>{holdingName(holding.instrument)} · {reviewStatus[holding.status]}</h4>
          <p>持仓权重 {percent(holding.weight_pct)}</p>
          <ul>{holding.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>
        </article>)}
      </section>
      <section className="cw-review-question">
        <h3>何时重新判断</h3>
        {holdings.map(holding => <article key={holding.instrument}>
          <h4>{holdingName(holding.instrument)}</h4>
          {holding.judgments.length ? <ul>{holding.judgments.map(judgment => <li key={judgment.note_id}>
            {judgment.comparator && judgment.threshold !== null && <p>收盘价{judgment.comparator === 'ABOVE' ? '达到或高于' : '达到或低于'} {judgment.threshold} 元</p>}
            {judgment.due_date && <p>复查日期 {judgment.due_date}{judgment.due_triggered && ' · 已到期'}</p>}
            {!judgment.price_only && <p>人工核对条件 · {judgment.invalidation}</p>}
            {(judgment.price_state === 'TRIGGERED' || judgment.state === 'TRIGGERED') && <strong>价格条件已触发</strong>}
          </li>)}</ul> : <p>没有已保存的复查条件，请在下方补记。</p>}
        </article>)}
      </section>
    </>}
  </>;
}

export function WorkbenchDailyReview() {
  const [reports, setReports] = useState<SavedReport[] | null>(null);
  const [selected, setSelected] = useState<SavedReport>();
  const [listRevision, setListRevision] = useState(0);
  const [listError, setListError] = useState('');
  const [result, setResult] = useState<{id: string; value?: DailyReview; error?: string}>();
  const [target, setTarget] = useState<JudgmentTarget>();
  const [formVersion, setFormVersion] = useState(0);
  const [saving, setSaving] = useState(false);
  const selectedId = selected?.report_id;
  const options = selected && !reports?.some(report => report.report_id === selectedId)
    ? [...(reports ?? []), selected]
    : reports;

  useEffect(() => {
    let active = true;
    request<SavedReport[]>('/daily-reports').then(items => {
      if (!active) return;
      setReports(items);
      setSelected(previous => previous ?? items[0]);
      setListError('');
    }).catch(error => {
      if (active) setListError(String(error));
    });
    return () => {active = false;};
  }, [listRevision]);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    request<DailyReview>(reportPath(selectedId) + '/review').then(value => {
      if (!active) return;
      if (value.report_id !== selectedId) {
        setResult({id: selectedId, error: '服务返回的报告版本与所选版本不一致。'});
      } else {
        setResult({id: selectedId, value});
      }
    }).catch(error => {
      if (active) setResult({id: selectedId, error: String(error)});
    });
    return () => {active = false;};
  }, [selectedId, listRevision]);

  const current = result?.id === selectedId ? result : undefined;
  return <div className="cw-daily-review">
    <div className="cw-card-head">
      <h2>日常复查</h2>
      <button type="button" disabled={saving} onClick={() => setListRevision(value => value + 1)}>重新读取报告列表</button>
    </div>
    <p className="cw-note">复查依据来自所选报告。你可以在「日常使用」生成或更新报告。</p>
    {listError && <p role="alert">报告列表读取失败 · {listError}</p>}
    {reports === null && !listError && <p role="status">正在读取报告列表…</p>}
    {!selected && reports?.length === 0 && <p>尚无已保存的日常报告。请先到「日常使用」生成一份。</p>}
    {selected && <>
      <label>报告版本
        <select disabled={saving} value={selected.report_id} onChange={event => {
          setSelected(options?.find(report => report.report_id === event.target.value));
          setResult(undefined);
          setTarget(undefined);
        }}>
          {options?.map(report => <option key={report.report_id} value={report.report_id}>{reportLabel(report)}</option>)}
        </select>
      </label>
      {!current && <p role="status">正在读取本版复查结果…</p>}
      {current?.error && <p role="alert">复查结果读取失败 · {current.error}</p>}
      {current?.value && <>
        <ReviewSections review={current.value} report={selected} saving={saving} onReview={value => {
          setTarget(value);
          setFormVersion(version => version + 1);
        }}/>
        {target && <button type="button" disabled={saving} onClick={() => setTarget(undefined)}>改为记录新判断</button>}
        <DailyJudgmentForm
          key={`${selected.report_id}:${target?.noteId ?? ''}:${formVersion}`}
          report={selected}
          target={target}
          onSavingChange={setSaving}
        />
      </>}
    </>}
  </div>;
}
