import {Funding} from '../api';
import '../styles/funding.css';
export const fundingState=(state:string)=>({UNCONFIRMED:'资金边界尚未确认',CONFIRMED:'资金边界已确认',PAUSED:'资金用途已暂停',REVOKED:'资金用途已撤回'}[state]??state);
export function FundingStatus({funding,compact=false}:{funding:Funding;compact?:boolean}){
  return <section><h2>资金授权</h2><p>{fundingState(funding.state)}</p>{funding.version>0&&<><p>资金授权版本 {funding.version}</p>{!compact&&<><p>{funding.purpose} · {funding.capital_amount} 元</p><p>总暴露上限 {funding.total_exposure} 元 · 单票 {funding.single_exposure} 元 · 现金保留 {funding.cash_reserve} 元</p><p>损失暂停阈值 {funding.loss_threshold} 元</p></>}</>}<p>损失与剩余额度待核：实际估值及现金流尚未接入</p></section>;
}
