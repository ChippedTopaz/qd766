import assert from 'node:assert/strict';
import {bindComparisonExports} from '../dist/comparison-export.js';
let header;
const title={textContent:'So với đơn vị cùng cấp',before(node){header=node}};
const peer={children:[]};
const card={querySelector(s){return s==='h3'?title:s==='.peer-row'?peer:null},matches:s=>s==='.comparison-card',querySelectorAll:()=>[peer]};
globalThis.document={
 querySelectorAll(s){return s==='.content .comparison-card'?[card]:[]},
 createElement(){return {className:'',textContent:'',children:[],attributes:{},handlers:{},
  setAttribute(k,v){this.attributes[k]=v},addEventListener(k,fn){this.handlers[k]=fn},
  append(...nodes){this.children.push(...nodes)}}}
};
bindComparisonExports({organization:'Xã mẫu',period:'Tháng 10/2026',scope:'Tất cả',updated:''},()=>{throw new Error('No automatic export')});
assert.equal(header.className,'peer-comparison-heading');
assert.equal(header.children[0],title);
assert.equal(header.children[1].textContent,'Tải Excel');
assert.equal(typeof header.children[1].handlers.click,'function');
console.log('PEER_EXPORT_HEADING_OK: title and Excel button in the same scoped flex header; export remains explicit');
