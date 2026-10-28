import {useEffect,useRef,useState} from 'react';
export function useChartSize(enabled:boolean,initial:{width:number;height:number}){
 const ref=useRef<SVGSVGElement>(null),[size,setSize]=useState(initial);
 useEffect(()=>{const element=ref.current;if(!enabled||!element)return;const update=()=>{const box=element.getBoundingClientRect();if(box.width>0&&box.height>0)setSize(old=>old.width===box.width&&old.height===box.height?old:{width:box.width,height:box.height})};update();const observer=new ResizeObserver(update);observer.observe(element);return()=>observer.disconnect()},[enabled]);
 return {ref,...size};
}
