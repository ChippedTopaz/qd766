/** Page-local only: no account data in persistent browser storage. */
export class RecentDashboard<T>{
 private entries=new Map<string,{expires:number;value:T}>();
 constructor(private ttl=30_000,private maximum=2,private clock=()=>Date.now()){}
 get(key:string):T|undefined{const entry=this.entries.get(key);if(!entry)return;if(entry.expires<=this.clock()){this.entries.delete(key);return;}this.entries.delete(key);this.entries.set(key,entry);return entry.value;}
 set(key:string,value:T){this.entries.delete(key);this.entries.set(key,{expires:this.clock()+this.ttl,value});while(this.entries.size>this.maximum)this.entries.delete(this.entries.keys().next().value!);}
}
