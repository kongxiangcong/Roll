export type Permission = {market:string;board:string;status:'OPEN'|'NOT_OPEN'|'UNKNOWN';basis:string;effective_at?:string;confirmed_at?:string;account_version?:number};
export type Position = {instrument:string;quantity:string;sellable_quantity:string|null;reference_cost:string|null;buy_time:null;historical_fees:null;acquisition_cost?:string|null;cost_basis?:string};
export type Fill = {record_id:string;fill_id:string|null;instrument:string;direction:string;quantity:string;price:string;fee:{status:string;amount:string|null;reserve_amount:string|null;basis:string};action_association:{status:string};receipt_id:string;effective_at:string};
export type Account = {version:number;cash_balance:string|null;broker_available:string|null;broker_frozen:string|null;withdrawable:string|null;positions:Position[];permission_profile:Permission[];confirmed_at:string|null;effective_at:string|null;state:string;fills?:Fill[];cash_balance_basis?:string;conservative_available?:string|null;conservative_available_basis?:string;broker_available_as_of?:string|null;broker_frozen_as_of?:string|null;withdrawable_as_of?:string|null;fee_resolutions?:Record<string,{actual_fee_amount:string}>};
export type Receipt = {receipt_id:string;draft_id:string;account_version:number;confirmed_at:string;event_ids:string[]};
export type Draft = {draft_id:string;preview:Record<string,{before:unknown;after:unknown}>;status?:string;issues?:string[];command?:{kind:string;payload:Record<string,unknown>}};
export async function request<T>(path:string, body?:unknown):Promise<T> {
  const response = await fetch(`/api${path}`,body===undefined ? undefined : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const value = await response.json();
  if(!response.ok) throw new Error(typeof value.detail==='string'?value.detail:JSON.stringify(value.detail));
  return value;
}
