import {useEffect,useState} from 'react';
import {request} from '../api';
type Model={model_run_id:string;status:string;purpose:string;evidence_kind:string;reasons:string[];model_artifact:{sha256:string}|null;calibrator_artifact:{sha256:string}|null;statistical_support?:{development_total:number;calibration_total:number;calibration_per_class:Record<string,number>;minimum_per_class:number};fit?:{weights:number[];feature_names:string[]};reliability?:unknown;baseline_comparison?:unknown;artifact_fingerprints?:Record<string,string>};
type Forecast={forecast_id:string;probability:number;uncalibrated_probability:number;event:string;horizon_sessions:number;observation_cutoff:string;consumer_knowledge_cutoff:string;baselines:unknown;return_scenarios:unknown;uncertainty:unknown;archive:{sha256:string}};
export function Models({protocolId,evidenceKind,calibrationFirstDate}:{protocolId:string;evidenceKind:string;calibrationFirstDate?:string}){
  const [models,setModels]=useState<Model[]>([]),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState(''),[date,setDate]=useState(calibrationFirstDate??''),[forecast,setForecast]=useState<Forecast|null>(null);
  async function refresh(){setModels(await request<Model[]>(`/research/protocols/${protocolId}/models`));}
  useEffect(()=>{void refresh().catch(e=>setError(String(e)));},[protocolId]);
  async function fit(){setBusy(true);setError('');try{await request(`/research/protocols/${protocolId}/models`,{purpose:evidenceKind==='METHOD_CASE'?'METHOD_VALIDATION':'RESEARCH',basis:'研究视图固定M0四特征/lambda1；失败计预算，未知不生成概率'});await refresh();setNotice('尝试已保留；工件及不足不会授予正式资格。');}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function predict(id:string){setBusy(true);setError('');try{setForecast(await request<Forecast>(`/research/models/${id}/forecasts`,{observation_date:date,basis:'固定CAL窗口方法预测；实际归档时间保留，不启动真实前向使用'}));}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function replay(){if(!forecast)return;try{const r=await request<{matches_original:boolean;network_calls:number}>(`/research/forecasts/${forecast.forecast_id}/replay`,{});setNotice(`${r.matches_original?'与原预测一致':'预测不一致'} · 联网 ${r.network_calls} 次`);}catch(e){setError(String(e));}}
  return <section aria-label="透明模型与研究预测"><h3>透明模型与研究预测</h3><p>固定四个量价特征 · L2 λ=1 · 20交易日费用后事件。仅开发/校准窗，完整实验尚未冻结，正式能力关闭。</p>
    <p>{evidenceKind==='METHOD_CASE'?'METHOD 数学工件验证；不能替代真实训练或独立校准验证。':'实际18标签支持检查；未知状态、公司行为及历史可得性不补成已知。'} 每次失败占五次拟合预算；截距校准最多一次。</p>
    <button disabled={busy} onClick={()=>void fit()}>登记并检查固定模型</button>
    {models.map(m=><article key={m.model_run_id}><h4>{m.status} · {m.purpose}</h4><p>{m.evidence_kind} · {m.model_run_id.slice(0,8)}</p>
      {m.statistical_support&&<p>开发可评分 {m.statistical_support.development_total} · 校准可评分 {m.statistical_support.calibration_total} · 每类要求 {m.statistical_support.minimum_per_class} · 当前 {JSON.stringify(m.statistical_support.calibration_per_class)}</p>}
      <ul>{m.reasons.map(r=><li key={r}>{r}</li>)}</ul>
      {m.model_artifact&&<p>模型 <a href={`/api/data/archives/${m.model_artifact.sha256}`} download>原工件 {m.model_artifact.sha256.slice(0,12)}</a> · 校准器 {m.calibrator_artifact?.sha256.slice(0,12)}</p>}
      {m.fit&&<details><summary>固定特征与权重</summary><pre>{JSON.stringify(m.fit,null,2)}</pre></details>}
      {!!m.reliability&&<details><summary>可靠性与支持度</summary><p>Brier、ROC或胜率改善不能宣称PASS。校准后统计使用同一校准窗，尚无独立验证；重叠20日期限不能当独立样本。</p><pre>{JSON.stringify(m.reliability,null,2)}</pre></details>}
      {!!m.baseline_comparison&&<details><summary>必要基线与经济比较边界</summary><p>CASH与固定MA逐机会对照保留。连续START_HOLD/NAV与风险比较尚未验收，不能把重叠逐单收益拼成财富。</p><pre>{JSON.stringify(m.baseline_comparison,null,2)}</pre></details>}
      {m.status==='METHOD_ARTIFACT_ONLY'&&<><label>方法观察日<input type="date" value={date} onChange={e=>setDate(e.target.value)}/></label><button disabled={busy||!date} onClick={()=>void predict(m.model_run_id)}>保存方法研究预测</button></>}
    </article>)}
    {forecast&&<article><h4>METHOD ForecastBundle</h4><p>费用后上涨事件 · {forecast.horizon_sessions}交易日 · 方法概率 {forecast.probability.toFixed(4)} · 原模型 {forecast.uncalibrated_probability.toFixed(4)}</p><p>观察截止 {forecast.observation_cutoff} · 实际消费知识截止 {forecast.consumer_knowledge_cutoff}。这次取得的事实不能回填为当时公开预测。</p><details><summary>情景、基线与限制</summary><pre>{JSON.stringify({event:forecast.event,baselines:forecast.baselines,return_scenarios:forecast.return_scenarios,uncertainty:forecast.uncertainty},null,2)}</pre></details><a href={`/api/data/archives/${forecast.archive.sha256}`} download>预测原件</a><button onClick={()=>void replay()}>原输入预测重放</button></article>}
    {notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
  </section>;
}
