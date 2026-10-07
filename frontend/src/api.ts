export type Permission = {market:string;board:string;status:'OPEN'|'NOT_OPEN'|'UNKNOWN';basis:string;effective_at?:string;confirmed_at?:string;account_version?:number};
export type Position = {instrument:string;quantity:string;sellable_quantity:string|null;reference_cost:string|null;buy_time:null;historical_fees:null};
export type Account = {version:number;cash_balance:string|null;broker_available:string|null;broker_frozen:string|null;withdrawable:string|null;positions:Position[];permission_profile:Permission[];confirmed_at:string|null;effective_at:string|null;state:string};
export type Receipt = {receipt_id:string;draft_id:string;account_version:number;confirmed_at:string;event_ids:string[]};
export type Draft = {draft_id:string;preview:Record<string,{before:unknown;after:unknown}>};
export type Funding = {version:number;state:string;loss_status:string;remaining_loss_allowance:string|null;scope_kind?:'ACCOUNT'|'TRIAL_ACTUAL';scope_id?:string;purpose?:string;capital_amount?:string;total_exposure?:string;single_exposure?:string;cash_reserve?:string;loss_threshold?:string;basis?:string;effective_at?:string;enabled?:boolean;pause_latched?:boolean;confirmed_at?:string};
export type Capability = {state:string;reason:string};
export type RuntimeHealth = {service:string;reason:string};
export async function request<T>(path:string, body?:unknown):Promise<T> {
  const response = await fetch(`/api${path}`,body===undefined ? undefined : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const value = await response.json();
  if(!response.ok) throw new Error(typeof value.detail==='string'?value.detail:JSON.stringify(value.detail));
  return value;
}
