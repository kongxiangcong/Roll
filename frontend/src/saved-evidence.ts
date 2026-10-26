import {request} from './api';

export async function savedEvidence<T>(instrument:string,kind:'status-evidence'|'action-evidence',cutoff:string):Promise<T[]>{
  const plans=await request<{plan_id:string;instrument:string}[]>('/research/collections');
  const params=cutoff?`?known_by=${encodeURIComponent(new Date(cutoff).toISOString())}`:'';
  return Promise.all(plans.filter(p=>p.instrument===instrument).map(p=>request<T>(`/research/collections/${p.plan_id}/${kind}${params}`)));
}
