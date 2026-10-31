(function(){
"use strict";

const diagrams=[{"slug": "01-runtime-overview", "title": "01 · 整体架构", "summary": "先看责任边界：入口驱动 Agent；循环调用模型与工具；Session 保存事实；实时 UI 使用单独的临时流。", "points": ["模型负责生成调用建议，真实执行留在宿主环境中。", "ctx.agents 是接口；ctx.agentLoop 是默认驱动，两者职责分离。", "蓝图折叠了部分插件，只保留主运行路径。"], "width": 1112}, {"slug": "02-agent-turn-loop", "title": "02 · 一轮任务", "summary": "沿主线看一轮工作：入队、组装、请求、工具、结果、继续。返回连线表示下一 Step 会使用刚得到的结果。", "points": ["Step 包含一次模型请求及其工具执行；请求可以有重试 attempt。", "Turn 可以有多个 Step，也可能在拒绝输入后以零个 Step 结束。", "光点是关系演示；实际顺序请对照下方的十步执行过程。"], "width": 1112}, {"slug": "03-plugin-composition", "title": "03 · 插件装配", "summary": "从启动组合看扩展：Profile 与 Bundle 装出宿主插件树；Preset 为 Agent 组织可见工具、提示词与技能。", "points": ["Plugin、Service、Tool、Skill 与 Preset 对应不同职责。", "注册项跟随生命周期清理，外部业务副作用不会因此自动撤销。", "Scope / Preset 管可见性，权限与租户隔离要在真实边界执行。"], "width": 1112}];
const assetBase=new URL('.',document.currentScript.src);
const guide=document.querySelector('.dsh-guide');
if(!guide)return;
guide.classList.add('dsh-enhanced');
const frame=document.getElementById('diagram-frame');
const viewport=document.querySelector('.diagram-viewport');
const tabButtons=[...document.querySelectorAll('[data-diagram]')];
let current=0,natural=false,paused=matchMedia('(prefers-reduced-motion: reduce)').matches,resizeObserver=null,animationStates=new WeakMap();
function syncHeight(){
 const doc=frame.contentDocument;
 if(!doc||!doc.getElementById('fit')) return;
 const fit=doc.getElementById('fit');
 const value=Math.ceil(fit.getBoundingClientRect().height+48);
 if(value>0) frame.style.height=value+'px';
}
function syncSize(){
 frame.style.width=natural?Math.max(diagrams[current].width,viewport.clientWidth)+'px':'100%';
 requestAnimationFrame(()=>{frame.contentWindow.dispatchEvent(new Event('resize'));syncHeight();});
 document.getElementById('size-toggle').textContent=natural?'适应宽度':'原尺寸';
 document.getElementById('size-toggle').setAttribute('aria-pressed',String(natural));
}
function syncPause(){
 const doc=frame.contentDocument;
 if(doc){
  for(const svg of doc.querySelectorAll('svg')){if(typeof svg.pauseAnimations==='function'){if(paused)svg.pauseAnimations();else svg.unpauseAnimations();}}
  for(const a of doc.getAnimations()){if(paused){if(a.playState==='running'){animationStates.set(a,true);a.pause();}}else if(animationStates.has(a)){a.play();animationStates.delete(a);}}
 }
 document.getElementById('pause-toggle').textContent=paused?'播放动画':'暂停动画';
 document.getElementById('pause-toggle').setAttribute('aria-pressed',String(paused));
}
function selectDiagram(index){
 current=index;
 const d=diagrams[index];
 tabButtons.forEach((b,i)=>{b.setAttribute('aria-selected',String(i===index));b.tabIndex=i===index?0:-1;});
 document.getElementById('diagram-panel').setAttribute('aria-labelledby','tab-'+index);
 document.getElementById('diagram-summary').textContent=d.summary;
 const list=document.getElementById('diagram-points');list.replaceChildren();
 d.points.forEach(p=>{const li=document.createElement('li');li.textContent=p;list.appendChild(li);});
 frame.title='DeepSeek Harness '+d.title+'动态图';
 if(resizeObserver)resizeObserver.disconnect();
 frame.src=new URL(d.slug+'.html',assetBase).href;
 viewport.scrollLeft=0;
}
frame.addEventListener('load',()=>{
 syncSize();syncHeight();syncPause();
 const target=frame.contentDocument.getElementById('fit');
 if(target&&typeof ResizeObserver!=='undefined'){resizeObserver=new ResizeObserver(syncHeight);resizeObserver.observe(target);}
 setTimeout(syncHeight,100);
});
tabButtons.forEach((b,i)=>{
 b.addEventListener('click',()=>selectDiagram(i));
 b.addEventListener('keydown',ev=>{
  if(ev.key==='ArrowRight'||ev.key==='ArrowLeft'){
   ev.preventDefault();const n=(i+(ev.key==='ArrowRight'?1:-1)+3)%3;selectDiagram(n);tabButtons[n].focus();
  }
 });
});
document.getElementById('size-toggle').addEventListener('click',()=>{natural=!natural;syncSize();});
document.getElementById('pause-toggle').addEventListener('click',()=>{paused=!paused;syncPause();});
addEventListener('resize',syncSize);
selectDiagram(0);

})();
