# -*- coding: utf-8 -*-
"""
artifact-review-html · 通用「产物标注回收」生成器
-----------------------------------------------
把任意一批文件（manifest 描述）渲染进一个离线可开的单 HTML，
内嵌「选中文字→标注/高亮→保存为固定名 JSON」的审阅引擎。

用法:
  python gen_review.py --manifest manifest.json --out review.html

依赖:
  pip install markdown   (已装进受管 venv 即可)
"""
import os, sys, json, subprocess, argparse, base64, shutil

ENGINE_JS = r"""
const STORE_KEY = 'artifact-review-v1';
let annotations = load();
let idSeq = Date.now();
let currentBatch = null;
let pendingImage = null;

function load(){ try { return JSON.parse(localStorage.getItem(STORE_KEY)||'[]'); } catch(e){ return []; } }
function save(){ localStorage.setItem(STORE_KEY, JSON.stringify(annotations)); }
function uid(){ return 'a' + (idSeq++); }
function esc(s){ return (s||'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

const content = document.getElementById('content');
const toolbar = document.getElementById('atb');
const inputBox = document.getElementById('ainput');
let pendingRange = null;

document.addEventListener('mouseup', function(e){
  if(e.target.closest('#atb') || e.target.closest('#ainput') || e.target.closest('#panel') || e.target.closest('.modal')) return;
  const sel = window.getSelection();
  if(!sel || sel.isCollapsed || sel.rangeCount === 0){ hideToolbar(); return; }
  const range = sel.getRangeAt(0);
  if(!range.toString().trim()){ hideToolbar(); return; }
  if(!content.contains(range.commonAncestorContainer)){ hideToolbar(); return; }
  pendingRange = range.cloneRange();
  const rect = range.getBoundingClientRect();
  toolbar.style.display = 'flex';
  let top = rect.top - toolbar.offsetHeight - 8 + window.scrollY;
  let left = rect.left + window.scrollX;
  if(top < 0) top = rect.bottom + 10 + window.scrollY;
  toolbar.style.top = top + 'px';
  toolbar.style.left = left + 'px';
});
document.addEventListener('mousedown', function(e){
  if(!e.target.closest('#atb') && !e.target.closest('#ainput') && !e.target.closest('.modal')) hideInput();
});
function hideToolbar(){ toolbar.style.display = 'none'; }
function hideInput(){ inputBox.style.display = 'none'; inputBox.querySelector('textarea').value=''; }

toolbar.querySelector('[data-act="note"]').addEventListener('click', function(){
  if(!pendingRange) return;
  const rect = pendingRange.getBoundingClientRect();
  inputBox.style.display = 'block';
  inputBox.style.top = (rect.bottom + 8 + window.scrollY) + 'px';
  inputBox.style.left = (rect.left + window.scrollX) + 'px';
  inputBox.dataset.mode = 'note';
  inputBox.querySelector('textarea').focus();
});
toolbar.querySelector('[data-act="hl"]').addEventListener('click', function(){
  if(!pendingRange) return;
  doWrap(pendingRange, '', 'hl');
  pendingRange = null; hideToolbar();
});
inputBox.querySelector('[data-act="save"]').addEventListener('click', function(){
  const v = inputBox.querySelector('textarea').value.trim();
  if(!v){ hideInput(); return; }
  if(inputBox.dataset.mode === 'image'){ commitImageAnno(v); hideInput(); return; }
  doWrap(pendingRange, v, 'note');
  hideInput(); pendingRange = null; hideToolbar();
});
inputBox.querySelector('[data-act="cancel"]').addEventListener('click', hideInput);

function getTextNodes(range){
  const nodes = [];
  const walker = document.createTreeWalker(content, NodeFilter.SHOW_TEXT, null);
  let n;
  while(n = walker.nextNode()){
    if(range.intersectsNode(n)){
      let s = 0, e = n.nodeValue.length;
      if(n === range.startContainer) s = range.startOffset;
      if(n === range.endContainer) e = range.endOffset;
      if(s < e) nodes.push({node:n, s, e});
    }
  }
  return nodes;
}
function doWrap(range, comment, type){
  if(!range) return;
  const parts = getTextNodes(range);
  if(!parts.length) return;
  const sec = parts[0].node.parentNode.closest('section[data-doc]');
  const grp = parts[0].node.parentNode.closest('.batch-group');
  const doc = sec ? sec.dataset.doc : 'unknown';
  const title = sec ? sec.dataset.title : '';
  const realpath = sec ? sec.dataset.realpath : '';
  const batchId = grp ? grp.dataset.batch : '';
  const batchLabel = grp ? grp.dataset.label : '';
  const quote = range.toString().trim().slice(0, 400);
  const id = uid();
  for(const p of parts){
    const node = p.node, text = node.nodeValue;
    const mid = text.slice(p.s, p.e), before = text.slice(0, p.s), after = text.slice(p.e);
    const parent = node.parentNode, frag = document.createDocumentFragment();
    if(before) frag.appendChild(document.createTextNode(before));
    const mark = document.createElement('mark');
    mark.className = 'anno' + (type === 'hl' ? ' hl' : '');
    mark.dataset.id = id; mark.textContent = mid;
    mark.title = type === 'hl' ? '高亮' : comment;
    frag.appendChild(mark);
    if(after) frag.appendChild(document.createTextNode(after));
    parent.replaceChild(frag, node);
  }
  annotations.push({id, batchId, batchLabel, doc, title, realpath, quote, comment, type, ts: new Date().toISOString()});
  save(); renderPanel();
}

function renderPanel(){
  const list = document.getElementById('comment-list');
  document.getElementById('cnt').textContent = annotations.length;
  if(!annotations.length){ list.innerHTML = '<p class="empty">还没有标注。选中正文里的文字即可标注。</p>'; return; }
  annotations.sort((a,b)=> a.ts < b.ts ? -1 : 1);
  list.innerHTML = annotations.map(a=>{
    const tag = a.type === 'img' ? '<span class="badge img">图</span>' : (a.type === 'hl' ? '<span class="badge hl">高亮</span>' : '<span class="badge">意见</span>');
    const c = a.comment ? esc(a.comment).replace(/\n/g,'<br>') : (a.type === 'img' ? '<em>（图片圈注）</em>' : '<em>（仅高亮）</em>');
    const q = esc(a.quote);
    const rp = a.realpath ? '<div class="rp">'+esc(a.realpath)+'</div>' : '<div class="rp" style="color:#b00">（自助添加·无 realpath）</div>';
    const region = a.region ? '<div class="rp">圈注位置：左上('+(a.region.x*100).toFixed(0)+'%,'+(a.region.y*100).toFixed(0)+'%) 宽'+(a.region.w*100).toFixed(0)+'% 高'+(a.region.h*100).toFixed(0)+'%</div>' : '';
    return `<div class="citem" data-id="${a.id}">
      <div class="crow"><span class="doc">${esc(a.title||a.batchLabel)}</span>${tag}<span class="del" data-id="${a.id}">删除</span></div>
      <div class="quote">“${q}”</div>${rp}${region}<div class="comm">${c}</div>
    </div>`;
  }).join('');
  list.querySelectorAll('.citem').forEach(el=>{
    el.addEventListener('click', e=>{
      if(e.target.classList.contains('del')) return;
      const m = document.querySelector('mark[data-id="'+el.dataset.id+'"], .img-mark[data-id="'+el.dataset.id+'"]');
      if(m) m.scrollIntoView({behavior:'smooth', block:'center'});
    });
  });
  list.querySelectorAll('.del').forEach(el=>{
    el.addEventListener('click', e=>{ e.stopPropagation(); removeAnno(el.dataset.id); });
  });
}
function removeAnno(id){
  document.querySelectorAll('mark[data-id="'+id+'"]').forEach(m=>{
    const p = m.parentNode; p.replaceChild(document.createTextNode(m.textContent), m); p.normalize();
  });
  const im = document.querySelector('.img-mark[data-id="'+id+'"]');
  if(im) im.remove();
  annotations = annotations.filter(a=> a.id !== id);
  document.querySelectorAll('section.annotated').forEach(s=>{
    if(!annotations.some(a=> a.type==='img' && a.doc===s.dataset.doc)) s.classList.remove('annotated');
  });
  save(); renderPanel();
}

function exportJSON(){
  const data = {tool:'artifact-review-html', exportedAt:new Date().toISOString(), count:annotations.length, annotations};
  const blob = new Blob([JSON.stringify(data, null, 2)], {type:'application/json'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'review-comments.json';
  document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
  document.getElementById('status').textContent = '已下载 review-comments.json —— 请存到约定目录，然后告诉我「写完了」';
  document.getElementById('modal-text').value = JSON.stringify(data, null, 2);
  document.getElementById('modal').style.display = 'flex';
}
function clearAll(){
  if(!confirm('确定清空所有标注？此操作不可撤销（除非你已导出）。')) return;
  annotations.slice().forEach(a=> removeAnno(a.id));
}
function importJSON(file){
  const reader = new FileReader();
  reader.onload = function(){
    try{
      const data = JSON.parse(reader.result);
      const arr = data.annotations || [];
      arr.forEach(a=>{
        if(annotations.find(x=> x.id === a.id)) return;
        annotations.push(a);
        if(a.type === 'img' && a.region){
          const sec = document.querySelector('section[data-doc="'+a.doc+'"]');
          if(sec){
            const marks = sec.querySelector('.img-marks');
            const cx = (a.region.x + a.region.w/2)*100, cy = (a.region.y + a.region.h/2)*100;
            const mk = document.createElement('div'); mk.className='img-mark'; mk.dataset.id=a.id;
            mk.style.left=cx+'%'; mk.style.top=cy+'%';
            mk.textContent = (annotations.filter(x=>x.type==='img').length);
            marks.appendChild(mk); sec.classList.add('annotated');
          }
        } else if(a.quote){ findAndWrap(a.quote, a.id, a.type, a.batchId); }
      });
      save(); renderPanel();
      alert('已导入 '+arr.length+' 条标注。');
    }catch(e){ alert('导入失败：'+e.message); }
  };
  reader.readAsText(file);
}
function findAndWrap(quote, id, type, batchId){
  const bodies = batchId ? [document.querySelector('.batch-group[data-batch="'+batchId+'"] .batch-body')] : Array.from(document.querySelectorAll('.batch-body'));
  const nodes = [];
  bodies.forEach(b=>{ if(!b) return; const w = document.createTreeWalker(b, NodeFilter.SHOW_TEXT, null); let n; while(n=w.nextNode()) nodes.push(n); });
  let buf = '', pos = null;
  outer: for(const node of nodes){
    const t = node.nodeValue;
    for(let i=0;i<t.length;i++){
      buf += t[i];
      if(buf.length > quote.length) buf = buf.slice(buf.length - quote.length);
      if(buf === quote){ pos = {node, off: i - quote.length + 1}; break outer; }
    }
  }
  if(!pos) return;
  const range = document.createRange();
  range.setStart(pos.node, pos.off < 0 ? 0 : pos.off);
  range.setEnd(pos.node, pos.off + quote.length);
  const parts = getTextNodes(range);
  for(const p of parts){
    const node = p.node, text = node.nodeValue;
    const mid = text.slice(p.s, p.e), before = text.slice(0,p.s), after = text.slice(p.e);
    const parent = node.parentNode, frag = document.createDocumentFragment();
    if(before) frag.appendChild(document.createTextNode(before));
    const mark = document.createElement('mark');
    mark.className = 'anno' + (type==='hl'?' hl':'');
    mark.dataset.id = id; mark.textContent = mid;
    frag.appendChild(mark);
    if(after) frag.appendChild(document.createTextNode(after));
    parent.replaceChild(frag, node);
  }
}

// 图片圈注（拖框定位 + 批注）
function enableImageAnno(){
  document.querySelectorAll('section[data-type="image"]').forEach(sec=>{
    const wrap = sec.querySelector('.img-wrap');
    const ov = sec.querySelector('.img-ov');
    let start = null, rectEl = null;
    ov.addEventListener('mousedown', function(e){
      e.preventDefault(); e.stopPropagation();
      const r = wrap.getBoundingClientRect();
      start = {x:e.clientX - r.left, y:e.clientY - r.top};
      rectEl = document.createElement('div'); rectEl.className='img-rect';
      rectEl.style.left=start.x+'px'; rectEl.style.top=start.y+'px'; rectEl.style.width='0px'; rectEl.style.height='0px';
      wrap.appendChild(rectEl);
    });
    ov.addEventListener('mousemove', function(e){
      if(!start) return;
      const r = wrap.getBoundingClientRect();
      const x=e.clientX - r.left, y=e.clientY - r.top;
      const left=Math.min(x,start.x), top=Math.min(y,start.y);
      rectEl.style.left=left+'px'; rectEl.style.top=top+'px';
      rectEl.style.width=Math.abs(x-start.x)+'px'; rectEl.style.height=Math.abs(y-start.y)+'px';
    });
    ov.addEventListener('mouseup', function(e){
      if(!start) return;
      const r = wrap.getBoundingClientRect();
      let x=e.clientX - r.left, y=e.clientY - r.top;
      let left=Math.min(x,start.x), top=Math.min(y,start.y);
      let w=Math.abs(x-start.x), h=Math.abs(y-start.y);
      if(w<10 && h<10){ left=0; top=0; w=r.width; h=r.height; }
      if(rectEl) rectEl.remove();
      const region = {x:left/r.width, y:top/r.height, w:w/r.width, h:h/r.height};
      pendingImage = {sec, region};
      inputBox.style.display='block';
      inputBox.style.top=(r.top + window.scrollY + top + h/2 + 8)+'px';
      inputBox.style.left=(r.left + window.scrollX + left)+'px';
      inputBox.dataset.mode='image';
      inputBox.querySelector('textarea').value=''; inputBox.querySelector('textarea').focus();
      start=null; rectEl=null;
    });
  });
}
function commitImageAnno(comment){
  if(!pendingImage) return;
  const {sec, region} = pendingImage;
  const grp = sec.closest('.batch-group');
  const doc = sec.dataset.doc, title = sec.dataset.title, realpath = sec.dataset.realpath;
  const batchId = grp?grp.dataset.batch:'', batchLabel = grp?grp.dataset.label:'';
  const id = uid();
  const marks = sec.querySelector('.img-marks');
  const cx=(region.x+region.w/2)*100, cy=(region.y+region.h/2)*100;
  const mk = document.createElement('div'); mk.className='img-mark'; mk.dataset.id=id;
  mk.style.left=cx+'%'; mk.style.top=cy+'%';
  mk.textContent = (annotations.filter(a=>a.type==='img').length+1);
  mk.title = comment;
  marks.appendChild(mk);
  sec.classList.add('annotated');
  annotations.push({id, batchId, batchLabel, doc, title, realpath, quote:'[图片圈注] '+title, comment, type:'img', region, ts:new Date().toISOString()});
  save(); renderPanel();
  pendingImage=null;
}

// 批次折叠 / 导航
function toggleBatch(grp){
  const body = grp.querySelector('.batch-body');
  const hidden = body.hasAttribute('hidden');
  body.toggleAttribute('hidden');
  grp.querySelector('.batch-head').classList.toggle('collapsed', !hidden);
  if(!hidden) currentBatch = grp.dataset.batch;
  renderNav();
}
function renderNav(){
  const nav = document.getElementById('nav');
  let html = '';
  document.querySelectorAll('.batch-group').forEach(grp=>{
    const body = grp.querySelector('.batch-body');
    if(body.hasAttribute('hidden')) return;
    grp.querySelectorAll('section[data-doc]').forEach(sec=>{
      const id = sec.id, label = sec.dataset.title;
      html += '<a href="#'+id+'">· '+esc(label)+'</a>';
    });
  });
  nav.innerHTML = html;
  nav.querySelectorAll('a').forEach(a=>{
    a.addEventListener('click', e=>{ e.preventDefault(); const t=document.querySelector(a.getAttribute('href')); if(t) t.scrollIntoView({behavior:'smooth', block:'start'}); });
  });
}

// 自助添加
const addModal = document.getElementById('add-modal');
document.getElementById('btn-add').addEventListener('click', ()=>{ addModal.style.display='flex'; });
document.getElementById('add-close').addEventListener('click', ()=> addModal.style.display='none');
document.getElementById('add-tab-file').addEventListener('click', ()=>{ document.getElementById('add-file-row').style.display='block'; document.getElementById('add-paste-row').style.display='none'; });
document.getElementById('add-tab-paste').addEventListener('click', ()=>{ document.getElementById('add-file-row').style.display='none'; document.getElementById('add-paste-row').style.display='block'; });
document.getElementById('add-file').addEventListener('change', e=>{
  const f = e.target.files[0]; if(!f) return;
  const r = new FileReader();
  r.onload = ()=> addSection(f.name, r.result);
  r.readAsText(f);
});
document.getElementById('add-paste-go').addEventListener('click', ()=>{
  const title = document.getElementById('add-title').value.trim() || ('自助添加 '+(document.querySelectorAll('section[data-doc^="user-"]').length+1));
  const text = document.getElementById('add-text').value;
  if(!text.trim()){ alert('请填写内容'); return; }
  addSection(title, text, true);
});
function renderContent(text, name){
  const lower = (name||'').toLowerCase();
  if(lower.endsWith('.md') || lower.endsWith('.txt')) return md(text);
  if(lower.endsWith('.json')) return '<pre><code>'+esc(text)+'</code></pre>';
  if(lower.endsWith('.py')||lower.endsWith('.cjs')||lower.endsWith('.js')) return '<pre><code>'+esc(text)+'</code></pre>';
  return '<pre>'+esc(text)+'</pre>';
}
function md(text){
  // lightweight: rely on global markdownit-like? use a tiny converter fallback
  // we embed marked? Not available offline; use server-rendered is preferred. For client paste, do minimal.
  return '<div class="md-fallback">'+esc(text).replace(/\n/g,'<br>')+'</div>';
}
function addSection(title, text, isText){
  const target = document.querySelector('.batch-group[data-batch="'+currentBatch+'"] .batch-body') || document.querySelector('.batch-body:not([hidden])') || document.querySelector('.batch-body');
  const n = document.querySelectorAll('section[data-doc^="user-"]').length + 1;
  const id = 'user-'+n;
  const body = renderContent(text, isText ? title+'.md' : title);
  const sec = document.createElement('section');
  sec.className = 'doc'; sec.id = id;
  sec.setAttribute('data-doc', id); sec.setAttribute('data-title', title); sec.setAttribute('data-realpath', '');
  sec.innerHTML = '<h2 class="doc-title">'+esc(title)+' <span class="ustag">（自助添加）</span></h2><div class="doc-body">'+body+'</div>';
  target.appendChild(sec);
  renderNav();
  addModal.style.display='none';
  sec.scrollIntoView({behavior:'smooth', block:'start'});
}

document.getElementById('btn-export').addEventListener('click', exportJSON);
document.getElementById('btn-clear').addEventListener('click', clearAll);
document.getElementById('btn-import').addEventListener('click', ()=> document.getElementById('file-import').click());
document.getElementById('file-import').addEventListener('change', e=>{ if(e.target.files[0]) importJSON(e.target.files[0]); });
document.getElementById('modal-close').addEventListener('click', ()=> document.getElementById('modal').style.display='none');
document.querySelectorAll('.batch-head').forEach(h=> h.addEventListener('click', ()=> toggleBatch(h.closest('.batch-group'))));

renderNav();
renderPanel();
enableImageAnno();
"""

TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  :root{ --bg:#f5f6f8; --card:#fff; --ink:#1d1d1f; --sub:#6b6b70; --line:#e3e5e8; --brand:#c0392b; --hl:#fff3a0; --hl2:#ffe08a; }
  *{ box-sizing:border-box; }
  body{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif; background:var(--bg); color:var(--ink); }
  header{ position:sticky; top:0; z-index:50; background:rgba(255,255,255,.92); backdrop-filter:blur(10px); border-bottom:1px solid var(--line); padding:10px 18px; display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
  header h1{ font-size:15px; margin:0; font-weight:700; }
  header .spacer{ flex:1; }
  header button{ font:inherit; font-size:12px; border:1px solid var(--line); background:#fff; border-radius:8px; padding:6px 10px; cursor:pointer; }
  header button:hover{ background:#f0f1f3; }
  #status{ font-size:12px; color:var(--brand); min-width:240px; }
  .layout{ display:flex; align-items:flex-start; }
  .nav{ position:sticky; top:53px; width:210px; flex:none; padding:14px 10px; font-size:13px; border-right:1px solid var(--line); height:calc(100vh - 53px); overflow:auto; }
  .nav .navhint{ font-size:11px; color:var(--sub); margin-bottom:8px; }
  .nav a{ display:block; color:var(--ink); text-decoration:none; padding:6px 9px; border-radius:8px; line-height:1.35; }
  .nav a:hover{ background:#eceef1; }
  #content{ flex:1; padding:18px 22px 140px; max-width:940px; margin:0 auto; }
  .batch-group{ margin-bottom:8px; }
  .batch-head{ width:100%; text-align:left; font:inherit; font-size:14px; font-weight:700; color:var(--brand); background:#fff; border:1px solid var(--line); border-radius:12px; padding:11px 14px; cursor:pointer; margin-bottom:10px; }
  .batch-head.collapsed::before{ content:"👉 "; }
  .batch-head:not(.collapsed)::before{ content:"👇 "; }
  .batch-body[hidden]{ display:none; }
  .doc{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:18px 22px; margin-bottom:20px; box-shadow:0 1px 3px rgba(0,0,0,.04); }
  .doc-title{ margin:0 0 4px; font-size:18px; }
  .ustag{ font-size:11px; color:#b00; font-weight:400; }
  .doc-meta{ font-size:12px; color:var(--sub); margin-bottom:12px; }
  .doc-meta code{ background:#f0f1f3; padding:1px 5px; border-radius:5px; word-break:break-all; }
  .doc-body{ line-height:1.7; font-size:14.5px; }
  .doc-body h1,.doc-body h2,.doc-body h3{ line-height:1.35; }
  .doc-body h2{ font-size:17px; border-bottom:1px solid var(--line); padding-bottom:4px; }
  .doc-body code{ background:#f0f1f3; padding:1px 5px; border-radius:5px; font-size:13px; }
  .doc-body pre{ background:#1e1e24; color:#f5f5f5; padding:12px 14px; border-radius:10px; overflow:auto; font-size:12.5px; }
  .doc-body pre code{ background:none; color:inherit; padding:0; }
  .doc-body table{ border-collapse:collapse; width:100%; font-size:13px; }
  .doc-body th,.doc-body td{ border:1px solid var(--line); padding:6px 9px; }
  .doc-body blockquote{ border-left:3px solid var(--hl2); margin:10px 0; padding:4px 12px; color:var(--sub); background:#fafafa; }
  mark.anno{ background:var(--hl); border-radius:3px; padding:0 1px; cursor:pointer; }
  mark.anno.hl{ background:var(--hl2); }
  mark.anno:hover{ outline:1px solid var(--brand); }
  #atb{ position:absolute; z-index:80; display:none; background:#1d1d1f; border-radius:10px; padding:4px; gap:4px; }
  #atb button{ background:transparent; color:#fff; border:none; font:inherit; font-size:12px; padding:6px 10px; border-radius:7px; cursor:pointer; }
  #atb button:hover{ background:#3a3a3f; }
  #ainput{ position:absolute; z-index:90; display:none; background:#fff; border:1px solid var(--line); border-radius:12px; padding:10px; box-shadow:0 8px 30px rgba(0,0,0,.18); width:300px; }
  #ainput textarea{ width:100%; height:64px; resize:vertical; font:inherit; font-size:13px; padding:6px; border:1px solid var(--line); border-radius:8px; }
  #ainput .row{ display:flex; gap:8px; justify-content:flex-end; margin-top:8px; }
  #ainput .row button{ font:inherit; font-size:12px; border:1px solid var(--line); border-radius:8px; padding:5px 12px; cursor:pointer; }
  #ainput .row .save{ background:var(--brand); color:#fff; border-color:var(--brand); }
  #panel{ position:sticky; top:53px; width:300px; flex:none; height:calc(100vh - 53px); overflow:auto; border-left:1px solid var(--line); padding:14px; background:#fafbfc; }
  .panel-head{ display:flex; align-items:center; gap:8px; margin-bottom:10px; }
  .panel-head h3{ margin:0; font-size:14px; flex:1; }
  .citem{ background:#fff; border:1px solid var(--line); border-radius:10px; padding:9px 11px; margin-bottom:10px; cursor:pointer; }
  .citem:hover{ border-color:var(--hl2); }
  .crow{ display:flex; align-items:center; gap:6px; font-size:11px; margin-bottom:5px; }
  .crow .doc{ color:var(--brand); font-weight:600; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .crow .del{ color:#b00; cursor:pointer; }
  .badge{ background:#eee; color:#555; padding:1px 6px; border-radius:6px; }
  .badge.hl{ background:var(--hl2); color:#7a5a00; }
  .quote{ font-size:12px; color:var(--sub); border-left:2px solid var(--line); padding-left:7px; margin-bottom:5px; max-height:54px; overflow:hidden; }
  .rp{ font-size:10.5px; color:#888; word-break:break-all; margin-bottom:5px; }
  .comm{ font-size:13px; line-height:1.5; }
  .empty{ font-size:12px; color:var(--sub); }
  .modal{ display:none; position:fixed; inset:0; background:rgba(0,0,0,.4); z-index:200; align-items:center; justify-content:center; }
  .modal .box{ background:#fff; border-radius:14px; padding:18px; width:min(700px,92vw); max-height:86vh; display:flex; flex-direction:column; }
  .modal h3{ margin:0 0 10px; font-size:15px; }
  .modal textarea{ flex:1; min-height:300px; font-family:ui-monospace,Menlo,monospace; font-size:12px; border:1px solid var(--line); border-radius:8px; padding:8px; }
  .modal .row{ display:flex; justify-content:flex-end; gap:10px; margin-top:10px; }
  .modal .row button{ font:inherit; font-size:13px; border:1px solid var(--line); border-radius:8px; padding:7px 14px; cursor:pointer; }
  .modal .row .ok{ background:var(--brand); color:#fff; border-color:var(--brand); }
  #add-modal .box{ width:min(560px,92vw); }
  #add-modal textarea{ width:100%; height:160px; font:inherit; font-size:13px; border:1px solid var(--line); border-radius:8px; padding:8px; }
  #add-modal input[type=text]{ width:100%; font:inherit; font-size:13px; border:1px solid var(--line); border-radius:8px; padding:6px; margin-bottom:8px; }
  .hidden-file{ display:none; }
  .img-doc .doc-body{ text-align:center; }
  .img-wrap{ position:relative; display:inline-block; max-width:100%; line-height:0; }
  .prod-img{ max-width:100%; display:block; border-radius:10px; }
  .img-ov{ position:absolute; inset:0; cursor:crosshair; }
  .img-marks{ position:absolute; inset:0; pointer-events:none; }
  .img-mark{ position:absolute; transform:translate(-50%,-50%); width:22px; height:22px; border-radius:50%; background:var(--brand); color:#fff; font-size:12px; display:flex; align-items:center; justify-content:center; border:2px solid #fff; box-shadow:0 1px 4px rgba(0,0,0,.4); pointer-events:auto; cursor:pointer; }
  .img-mark:hover{ outline:2px solid var(--hl2); }
  .img-hint{ position:absolute; left:8px; bottom:8px; background:rgba(0,0,0,.55); color:#fff; font-size:11px; padding:3px 8px; border-radius:6px; }
  .img-doc.annotated{ outline:2px solid var(--brand); }
  .img-rect{ position:absolute; border:2px solid var(--brand); background:rgba(192,57,43,.18); pointer-events:none; }
  .badge.img{ background:var(--brand); color:#fff; }
</style>
</head>
<body>
<header>
  <h1>__TITLE__</h1>
  <span id="status"></span>
  <span class="spacer"></span>
  <button id="btn-export">⬇ 保存并下载</button>
  <button id="btn-import">⬆ 导入</button>
  <button id="btn-add">➕ 自助添加</button>
  <button id="btn-clear">清空</button>
  <input type="file" id="file-import" class="hidden-file" accept="application/json">
</header>
<div class="layout">
  <nav class="nav"><div class="navhint">目录（仅显示展开的批次）</div><div id="nav"></div></nav>
  <main id="content">__BATCHES__</main>
  <aside id="panel">
    <div class="panel-head"><h3>标注 / 意见（<span id="cnt">0</span>）</h3></div>
    <div id="comment-list"></div>
  </aside>
</div>

<div id="atb"><button data-act="note">💬 标注</button><button data-act="hl">🖍 高亮</button></div>
<div id="ainput"><textarea placeholder="写下你的意见（这条会被逐条改到产物里）…"></textarea><div class="row"><button data-act="cancel">取消</button><button data-act="save" class="save">保存标注</button></div></div>

<div id="modal" class="modal"><div class="box"><h3>导出的意见（也可直接复制发我）</h3><textarea id="modal-text" readonly></textarea><div class="row"><button id="modal-close">关闭</button></div></div></div>

<div id="add-modal" class="modal"><div class="box">
  <h3>自助添加产物</h3>
  <div style="margin-bottom:8px;">
    <button id="add-tab-file" style="font:inherit;font-size:12px;border:1px solid var(--line);border-radius:8px;padding:5px 10px;cursor:pointer;">上传文件</button>
    <button id="add-tab-paste" style="font:inherit;font-size:12px;border:1px solid var(--line);border-radius:8px;padding:5px 10px;cursor:pointer;">粘贴文本</button>
  </div>
  <div id="add-file-row"><input type="file" id="add-file" accept=".md,.txt,.json,.py,.cjs,.js,.text"></div>
  <div id="add-paste-row" style="display:none;">
    <input type="text" id="add-title" placeholder="标题（如：补充一份竞品分析）">
    <textarea id="add-text" placeholder="粘贴内容…"></textarea>
  </div>
  <div class="row"><button id="add-close">取消</button><button id="add-paste-go" class="ok" style="font:inherit;font-size:13px;border:1px solid var(--brand);background:var(--brand);color:#fff;border-radius:8px;padding:7px 14px;cursor:pointer;">添加</button></div>
</div></div>

<script>
__ENGINE__
</script>
</body>
</html>
"""

LANG = {'.json':'json', '.py':'python', '.cjs':'javascript', '.js':'javascript', '.txt':'text', '.md':'markdown'}
IMAGE_EXTS = {'.png','.jpg','.jpeg','.gif','.webp','.bmp'}

def render_file(root, f):
    src = f['src']; docid = f.get('docid', src); title = f.get('title', src)
    realpath = f.get('realpath') or os.path.join(root, src)
    full = os.path.join(root, src)
    ext = os.path.splitext(src)[1].lower()
    if ext in IMAGE_EXTS:
        with open(full, 'rb') as fh:
            b64 = base64.b64encode(fh.read()).decode('ascii')
        mime = 'image/png' if ext == '.png' else ('image/jpeg' if ext in ('.jpg', '.jpeg') else 'image/' + ext.lstrip('.'))
        body = ('<div class="img-wrap"><img class="prod-img" src="data:%s;base64,%s" alt="%s">'
                '<div class="img-ov"></div><div class="img-marks"></div>'
                '<div class="img-hint">在图上拖框即可圈注这张图（单击=整图批注）</div></div>') % (mime, b64, title)
        return ('<section class="doc img-doc" id="doc-%s" data-doc="%s" data-title="%s" data-realpath="%s" data-type="image">'
                '<h2 class="doc-title">%s <span class="imgtag">（图片产物）</span></h2>'
                '<div class="doc-meta">真实文件：<code>%s</code></div>'
                '<div class="doc-body">%s</div></section>') % (
            docid, docid, title, realpath, title, realpath, body)
    with open(full, encoding='utf-8') as fh:
        text = fh.read()
    if ext == '.md':
        body = markdown.markdown(text, extensions=['fenced_code','tables','toc','sane_lists'])
    elif ext in ('.json', '.py', '.cjs', '.js', '.txt'):
        lang = LANG.get(ext, 'text')
        body = '<pre><code>' + text.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;') + '</code></pre>'
    else:
        body = '<pre>' + text.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;') + '</pre>'
    return ('<section class="doc" id="doc-%s" data-doc="%s" data-title="%s" data-realpath="%s">'
            '<h2 class="doc-title">%s</h2>'
            '<div class="doc-meta">真实文件：<code>%s</code></div>'
            '<div class="doc-body">%s</div></section>') % (
        docid, docid, title, realpath, title, realpath, body)

def build_batches(manifest):
    groups = []
    for b in manifest['batches']:
        bid = b['id']; label = b['label']; root = b['root']
        default = b.get('default', False)
        sections = '\n'.join(render_file(root, f) for f in b['files'])
        hidden = '' if default else ' hidden'
        collapsed = '' if default else ' collapsed'
        groups.append(
            '<div class="batch-group" data-batch="%s" data-label="%s">'
            '<button class="batch-head%s">%s（%d 项）</button>'
            '<div class="batch-body"%s>%s</div></div>' % (
                bid, label, collapsed, label, len(b['files']), hidden, sections))
    return '\n'.join(groups)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--manifest', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--title', default=None)
    args = ap.parse_args()

    with open(args.manifest, encoding='utf-8') as fh:
        manifest = json.load(fh)
    title = args.title or manifest.get('title', '产物审阅件')

    batches_html = build_batches(manifest)

    # node syntax check on ENGINE_JS (best-effort: only if a node binary is found)
    node_bin = find_node()
    if node_bin:
        tmpjs = '/tmp/_review_engine.js'
        with open(tmpjs, 'w', encoding='utf-8') as fh:
            fh.write(ENGINE_JS)
        r = subprocess.run([node_bin, '--check', tmpjs], capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit('JS 语法错误:\n' + r.stderr)
    else:
        print('[warn] 未找到 node，跳过内联 JS 语法校验（输出仍会生成，但请人工确认 JS 无语法错误）')

    html = (TEMPLATE
            .replace('__TITLE__', title)
            .replace('__BATCHES__', batches_html)
            .replace('__ENGINE__', ENGINE_JS))

    with open(args.out, 'w', encoding='utf-8') as fh:
        fh.write(html)
    print('written:', args.out, '|', os.path.getsize(args.out), 'bytes | batches:', len(manifest['batches']))

def find_node():
    """优先用本机受管 node，否则回退系统 PATH 里的 node，都没有返回 None。"""
    candidates = [
        '/Users/yanhao/.workbuddy/binaries/node/versions/22.22.2-3/bin/node',
        shutil.which('node'),
    ]
    for n in candidates:
        if n and os.path.exists(n):
            return n
    return None


if __name__ == '__main__':
    import markdown
    main()
