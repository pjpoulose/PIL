#!/usr/bin/env python3
"""PIL step 5: export the library as a self-contained HTML dashboard.

Reads the local SQLite database (read-only) and writes one HTML file with
everything inline: masthead + stats, client-side search, rooms sidebar,
popular tags, sortable card grid, and expandable read-notes per post.

Usage:
    python3 export_html.py [output_path]   # defaults to <data_dir>/pil_library.html

Open the file in any browser (double-click works). It needs no network:
all data is embedded. Save it to your Desktop and use your browser's
"Create shortcut / Add to Dock" to keep it like a desktop web app.
"""
import html
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pil_common import db_connect, load_config

PAGE_SIZE = 60
PALETTE = ["#4A2B28", "#2E3A30", "#2B2E45", "#3A362A", "#3A2A3E",
           "#2A3B3B", "#43301F", "#33302B", "#3E2A2E"]


def q(db, sql, args=()):
    db.row_factory = None
    cur = db.execute(sql, args)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
__PWA_HEAD__
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#141414;color:#EDE8DB;font-family:-apple-system,"Segoe UI",Inter,sans-serif;-webkit-font-smoothing:antialiased}
.serif{font-family:Georgia,"Times New Roman",serif}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11px;letter-spacing:2.5px;text-transform:uppercase}
.wrap{max-width:1360px;margin:0 auto;padding:0 48px 90px}
.masthead{display:flex;justify-content:space-between;gap:40px;padding:64px 0 56px;flex-wrap:wrap}
.brand{color:#8A8578;margin-bottom:26px}
.brand b{color:#EDE8DB}
.brand .rule{color:#E0453A;margin-right:10px}
.masthead h1{font-family:Georgia,serif;font-weight:400;font-size:64px;line-height:1.12;letter-spacing:-.5px}
.masthead .lede{margin-top:22px;font-size:17px;line-height:1.6;color:#A39D8D;max-width:420px}
.index{width:340px;flex-shrink:0}
.index .top{display:flex;justify-content:space-between;color:#8A8578;border-top:1px solid #2B2B2B;padding-top:14px}
.bignum{font-family:Georgia,serif;font-size:76px;line-height:1;margin:14px 0 4px}
.bignum-sub{text-align:right;color:#8A8578}
.cov{border-top:1px solid #2B2B2B;margin-top:18px;padding-top:14px}
.cov .row1{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:12px}
.cov .row1 span:last-child{color:#6E695D;letter-spacing:1px;font-size:12px}
.covgrid{display:grid;grid-template-columns:1fr 1fr;gap:10px 20px}
.covgrid b{font-family:ui-monospace,monospace;font-size:15px;display:block}
.covgrid span{font-size:10px;letter-spacing:2px;color:#6E695D;text-transform:uppercase}
.totals{display:flex;border-top:1px solid #2B2B2B;margin-top:16px;padding-top:14px}
.totals div{flex:1}.totals div+div{border-left:1px solid #2B2B2B;padding-left:20px}
.totals b{font-family:Georgia,serif;font-size:24px;font-weight:400;display:block}
.totals span{font-size:10px;letter-spacing:2px;color:#6E695D;text-transform:uppercase}
.searchbar{background:#F2EEE2;border-radius:3px;display:flex;align-items:center;padding:20px 26px;margin-bottom:54px}
.searchbar input{flex:1;background:none;border:none;outline:none;font-family:Georgia,serif;font-style:italic;font-size:19px;color:#141414}
.searchbar input::placeholder{color:#8a8474}
.searchbar .kbd{border:1px solid #C9C3B2;color:#6E695D;font-size:13px;padding:4px 10px;border-radius:3px;font-family:ui-monospace,monospace}
.body{display:flex;gap:56px}
.side{width:220px;flex-shrink:0}
.side .label{color:#6E695D;margin-bottom:6px}
.room{display:flex;justify-content:space-between;align-items:center;width:100%;background:none;border:none;border-bottom:1px solid #242424;padding:11px 2px;font-size:14px;color:#C9C3B2;cursor:pointer;text-align:left;font-family:inherit}
.room .n{font-family:ui-monospace,monospace;font-size:12px;color:#6E695D}
.room.active{color:#EDE8DB;font-weight:600}
.room.active .dot{width:7px;height:7px;background:#E0453A;border-radius:50%;display:inline-block;margin-right:9px}
.tags-label{color:#6E695D;margin:34px 0 14px}
.tagchips{display:flex;flex-wrap:wrap;gap:8px}
.chip{border:1px solid #2B2B2B;background:none;color:#A39D8D;padding:8px 12px;font-family:ui-monospace,monospace;font-size:11px;cursor:pointer}
.chip.active{border-color:#E0453A;color:#EDE8DB}
.deepnotes{margin-top:26px;font-size:12px;color:#6E695D}
.deepnotes i{width:7px;height:7px;background:#E0453A;border-radius:50%;display:inline-block;margin-right:8px}
.main{flex:1;min-width:0}
.browse-head{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:34px;flex-wrap:wrap;gap:16px}
.browse-head h2{font-family:Georgia,serif;font-weight:400;font-size:44px}
.browse-head .sub{font-family:ui-monospace,monospace;font-size:12px;color:#6E695D;margin-top:8px}
.sort{display:flex;align-items:center;gap:12px;color:#6E695D}
.sort select{background:#141414;border:1px solid #2B2B2B;color:#C9C3B2;padding:10px 14px;font-family:ui-monospace,monospace;font-size:12px;letter-spacing:1px}
.card{margin-bottom:44px;position:relative}
.panel{border-radius:3px;padding:44px 48px;position:relative;overflow:hidden}
.panel::before{content:"";position:absolute;width:420px;height:420px;border:1px solid rgba(255,255,255,.07);border-radius:50%;right:-120px;top:-120px}
.panel .prow{display:flex;justify-content:space-between;margin-bottom:30px;position:relative}
.panel .prow .mono{color:rgba(237,232,219,.75)}
.pnum{font-family:ui-monospace,monospace;font-size:11px;letter-spacing:2px;color:rgba(237,232,219,.55)}
.panel h3{font-family:Georgia,serif;font-weight:400;font-size:40px;line-height:1.28;position:relative}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:0 40px}
.grid .panel{padding:34px 36px}.grid .panel h3{font-size:27px}
.meta{padding:18px 4px 0}
.meta .kind{color:#8A8578;margin-bottom:8px}
.meta .who{font-family:ui-monospace,monospace;font-size:13px;color:#C9C3B2}
.meta .rooms{font-family:ui-monospace,monospace;font-size:12px;color:#6E695D;margin-top:6px}
.meta .foot{display:flex;justify-content:space-between;border-top:1px solid #242424;margin-top:16px;padding-top:14px;font-size:13px;color:#8A8578}
.meta .foot button{background:none;border:none;color:#8A8578;font-size:13px;cursor:pointer;font-family:inherit;padding:0}
.meta .foot button:hover{color:#EDE8DB}
.meta .foot .ig{color:#A39D8D;text-decoration:none}
.notes{display:none;border-top:1px solid #242424;margin-top:14px;padding-top:18px}
.notes.open{display:block}
.notes h4{font-family:Georgia,serif;font-weight:400;font-size:20px;margin:0 0 10px}
.notes .sec{margin-bottom:16px}
.notes .sec .mono{color:#E0453A;display:block;margin-bottom:8px}
.notes p,.notes li{font-size:14px;line-height:1.65;color:#C9C3B2}
.notes ul{list-style:none}
.notes li{margin-bottom:8px;padding-left:18px;position:relative}
.notes li::before{content:"—";position:absolute;left:0;color:#E0453A}
.notes a{color:#EDE8DB}
.notes .mdh{font-family:Georgia,serif;font-size:17px;color:#EDE8DB;margin:14px 0 6px}
.notes strong{color:#EDE8DB;font-weight:600}
.card .rdot{position:absolute;right:-2px;top:46%;width:7px;height:7px;background:#E0453A;border-radius:50%}
.more{text-align:center;margin-top:20px}
.more button{background:none;border:1px solid #2B2B2B;padding:14px 30px;font-family:ui-monospace,monospace;font-size:12px;letter-spacing:2px;color:#A39D8D;cursor:pointer}
.more button:hover{border-color:#E0453A;color:#EDE8DB}
.empty{padding:80px 0;text-align:center;color:#6E695D;font-family:Georgia,serif;font-style:italic;font-size:20px}
.footer-note{text-align:center;margin-top:70px;padding-top:26px;border-top:1px solid #242424;font-size:11px;letter-spacing:2.5px;color:#6E695D;text-transform:uppercase}
@media(max-width:900px){.body{flex-direction:column}.side{width:100%}.grid{grid-template-columns:1fr}.masthead h1{font-size:44px}.wrap{padding:0 24px 60px}}
#answers{margin-bottom:26px}
.grounding{display:flex;align-items:center;gap:10px;font-family:ui-monospace,monospace;font-size:12px;color:#8A8578;margin:0 0 16px}
.grounding-dot{width:7px;height:7px;border-radius:50%;background:#E0453A;flex:0 0 auto}
.knowledge-grid{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:20px;align-items:start}
.answer-panel,.source-panel,.limited-panel{background:#161616;border:1px solid #2B2B2B;padding:28px 30px}
.answer-kicker{font-family:ui-monospace,monospace;font-size:11px;letter-spacing:2.5px;text-transform:uppercase;color:#E0453A;margin:0 0 10px}
.answer-title{font-family:Georgia,serif;font-weight:400;font-size:clamp(24px,3vw,34px);line-height:1.15;color:#EDE8DB;margin:0 0 14px}
.answer-lead{font-size:15px;line-height:1.7;color:#C9C3B2;margin:0 0 6px}
.answer-section{border-top:1px solid #242424;padding-top:20px;margin-top:22px}
.answer-section h3{font-family:Georgia,serif;font-weight:400;font-size:20px;color:#EDE8DB;margin:0 0 12px}
.takeaways{list-style:none;margin:0;padding:0}
.takeaways li{margin-bottom:10px;padding-left:18px;position:relative;font-size:14px;line-height:1.65;color:#C9C3B2}
.takeaways li::before{content:"—";position:absolute;left:0;color:#E0453A}
.takeaways strong{color:#EDE8DB}
.citation{display:inline-flex;align-items:center;justify-content:center;vertical-align:.15em;min-width:22px;height:22px;padding:0 6px;margin-left:8px;background:none;border:1px solid #E0453A;border-radius:11px;color:#E0453A;font-family:ui-monospace,monospace;font-size:11px;cursor:pointer}
.citation:hover{background:#E0453A;color:#141414}
.source-panel{padding:22px}
.source-head{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:14px}
.source-head h3{font-family:Georgia,serif;font-weight:400;font-size:18px;color:#EDE8DB;margin:0}
.source-count{font-family:ui-monospace,monospace;font-size:11px;color:#8A8578}
.source-list{display:grid;gap:10px}
.source-card{background:#1C1C1C;border:1px solid #2B2B2B;padding:14px 16px;text-align:left;font-family:inherit;cursor:pointer}
.source-card:hover{border-color:#E0453A}
.source-card-top{display:flex;justify-content:space-between;margin-bottom:8px}
.source-number{font-family:ui-monospace,monospace;font-size:11px;color:#E0453A}
.source-folder{font-family:ui-monospace,monospace;font-size:11px;color:#6E695D}
.source-author{font-size:13px;color:#EDE8DB;margin-bottom:6px}
.source-excerpt{font-size:13px;line-height:1.6;color:#8A8578;margin:0 0 8px}
.source-links{display:flex;gap:12px;align-items:center}
.source-links .ig{font-size:12px;color:#A39D8D;text-decoration:none}
.source-links .ig:hover{color:#EDE8DB}
.source-links .linknote{font-size:11px;color:#6E695D;font-family:ui-monospace,monospace}
.limited-panel p{font-size:14px;line-height:1.65;color:#C9C3B2}
.limited-panel .why-match{font-size:12px;color:#6E695D;font-family:ui-monospace,monospace;margin-top:14px}
.excerpt-card{border-top:1px solid #242424;padding:14px 0}
.excerpt-card h4{font-size:14px;color:#EDE8DB;margin:0 0 6px;font-weight:600}
.excerpt-card p{font-size:13px;line-height:1.65;color:#8A8578;margin:0}
.followups{display:flex;flex-wrap:wrap;gap:8px}
.followup{background:none;border:1px solid #2B2B2B;color:#A39D8D;font-family:ui-monospace,monospace;font-size:11px;letter-spacing:1px;padding:10px 16px;cursor:pointer}
.followup:hover{border-color:#E0453A;color:#EDE8DB}
.approach-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.approach{background:#1C1C1C;border:1px solid #2B2B2B;padding:16px 18px}
.approach strong{font-size:13px;color:#EDE8DB}
.approach p{font-size:13px;line-height:1.6;color:#8A8578;margin:8px 0 0}
.card.flash{outline:2px solid #E0453A;outline-offset:4px}
#phonepanel{border:1px solid #2B2B2B;background:#161616;padding:24px 28px;margin-bottom:26px;display:none;align-items:center;gap:24px}
#phonepanel.show{display:flex}
#phonepanel img{width:120px;height:120px;flex:0 0 auto;background:#fff;padding:6px}
#phonepanel h3{font-family:Georgia,serif;font-weight:400;font-size:20px;color:#EDE8DB;margin:0 0 8px}
#phonepanel p{font-size:13px;line-height:1.65;color:#8A8578;margin:0 0 6px}
#phonepanel a{color:#EDE8DB}
@media(max-width:900px){.knowledge-grid{grid-template-columns:1fr}.approach-grid{grid-template-columns:1fr}#phonepanel{flex-direction:column;align-items:flex-start}}
</style>
</head>
<body>
<div class="wrap">
  <div class="masthead">
    <div>
      <div class="brand mono"><span class="rule">—</span> <b>PIL</b> &nbsp;|&nbsp; PERSONAL INSTAGRAM LIBRARY</div>
      <h1>Rediscover what<br>caught your eye.</h1>
      <p class="lede">Search the ideas, tutorials, recipes, tools, and rabbit holes you saved for later.</p>
    </div>
    <div class="index">
      <div class="top mono"><span>PIL Index</span><span>Personal Library</span></div>
      <div class="bignum">__POSTS__</div>
      <div class="bignum-sub mono">Saved<br>posts</div>
      <div class="cov">
        <div class="row1"><span class="mono">Field coverage</span><span>Varies by post</span></div>
        <div class="covgrid">
          <div><b>__SUMMARIES__</b><span>Summaries</span></div>
          <div><b>__KEYPOINTS__</b><span>Key points</span></div>
          <div><b>__HOWTOS__</b><span>How-to guides</span></div>
          <div><b>__LINKS__</b><span>Links</span></div>
        </div>
      </div>
      <div class="totals">
        <div><b>__WITHKNOW__</b><span>Posts with knowledge</span></div>
        <div><b>__ROOMS__</b><span>Rooms</span></div>
      </div>
    </div>
  </div>

  <div id="phonepanel">
    <img id="phoneqr" alt="QR code to install PIL on your phone">
    <div>
      <h3>Take PIL on your phone</h3>
      <p>Scan the code with your phone's camera, or open this link on your phone:<br><a id="phonelink" href="#"></a></p>
      <p>Android: open in Chrome → Install app &nbsp;·&nbsp; iPhone: open in Safari → Share → Add to Home Screen. After the first load it works offline.</p>
    </div>
  </div>

  <div class="searchbar">
    <input id="q" type="text" placeholder="Search PIL…" autocomplete="off">
    <span class="kbd">/</span>
  </div>

  <div class="body">
    <div class="side">
      <div class="label mono">Rooms</div>
      <div id="rooms"></div>
      <div class="tags-label mono">Popular tags</div>
      <div class="tagchips" id="tags"></div>
      <div class="deepnotes"><i></i>Deep notes available</div>
    </div>
    <div class="main">
      <div class="browse-head">
        <div><h2 id="title">Browse PIL</h2><div class="sub" id="count"></div></div>
        <div class="sort mono">Sort
          <select id="sort"><option value="new">Recently saved</option><option value="old">Oldest saved</option></select>
        </div>
      </div>
      <div id="answers" style="display:none"></div>
      <div id="featured"></div>
      <div class="grid" id="grid"></div>
      <div class="empty" id="empty" style="display:none">Nothing in the library matches — try another search.</div>
      <div class="more"><button id="more">SHOW MORE</button></div>
    </div>
  </div>
  <div class="footer-note">__FOOTER__</div>
</div>

<script id="pil-data" type="application/json">__DATA__</script>
<script>
const PIL = JSON.parse(document.getElementById('pil-data').textContent);
const PALETTE = __PALETTE__;
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const md = s => {
  let e = esc(s).replace(/^#{2,3} (.*)$/gm, '<p class="mdh">$1</p>').replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  const lines = e.split('\n'), out = []; let inList = false;
  for(const ln of lines){
    const m = ln.match(/^\s*-\s+(.*)/);
    if(m){ if(!inList){ out.push('<ul>'); inList = true; } out.push('<li>'+m[1]+'</li>'); }
    else { if(inList){ out.push('</ul>'); inList = false; } if(ln.trim()) out.push('<p>'+ln+'</p>'); }
  }
  if(inList) out.push('</ul>');
  return out.join('');
};
const inlineMd = s => esc(s).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
const state = { q:'', room:null, tag:null, sort:'new', shown:__PAGE__ };
const folderName = id => (PIL.folders.find(f=>f.id===id)||{}).name || id;
PIL.posts.forEach((p,i)=>{
  p._index=i;
  const deep=[p.summary,(p.key_points||[]).join(' '),p.howto].filter(Boolean).join(' ');
  p._knowledgeText=deep.toLowerCase();
  p._text=[p.author,p.snippet,(p.tags||[]).join(' '),p.folders.map(folderName).join(' '),deep].join(' ').toLowerCase();
  p.has_knowledge=!!(p.summary||(p.key_points&&p.key_points.length)||p.howto);
});

const fmt = n => Number(n||0).toLocaleString();
function el(tag, cls, text){ const node=document.createElement(tag); if(cls) node.className=cls; if(text!==undefined) node.textContent=text; return node; }
function clean(v){
  return String(v||'')
    .replace(/^#{1,6}\s*/gm,'')
    .replace(/\*\*/g,'')
    .replace(/\bSocial Context\s*&\s*Synthesis\b/gi,'Context')
    .replace(/\bCultural Context\b/gi,'Context')
    .replace(/\bCultural Moment\b/gi,'Moment')
    .replace(/\bCultural Significance\b/gi,'Significance')
    .replace(/\bCultural Origin\b/gi,'Origin')
    .trim();
}
function shorten(v, max){ max=max||240; const t=clean(v).replace(/\s+/g,' '); return t.length>max ? t.slice(0,max-1).trim()+'…' : t; }
const GENERIC_TAGS = new Set(['video','carousel','image','they','here','most','every','time','know','full','want','need','send','part']);
function scorePost(p, terms){
  if(!terms.length) return 0;
  let score=0;
  const author=(p.author||'').toLowerCase(), snippet=(p.snippet||'').toLowerCase(),
        tags=(p.tags||[]).map(t=>String(t).toLowerCase()), phrase=terms.join(' ');
  for(const term of terms){
    if(!p._text.includes(term)) return -1;
    if(author.includes(term)) score+=5;
    if(tags.some(t=>t===term)) score+=7;
    if(tags.some(t=>t.includes(term))) score+=3;
    if(snippet.includes(term)) score+=3;
    if(p._knowledgeText.includes(term)) score+=4;
  }
  if(phrase.length>2){
    if(snippet.includes(phrase)) score+=10;
    if(p._knowledgeText.includes(phrase)) score+=12;
    if(tags.includes(phrase)) score+=12;
  }
  if(p.has_knowledge) score+=1;
  return score;
}
function sourceNumber(post, sources){ return Math.max(0, sources.findIndex(p=>p.id===post.id))+1; }
function jumpToSource(post){
  const t=document.getElementById('card-'+post.id);
  if(!t) return;
  t.scrollIntoView({behavior:'smooth', block:'center'});
  t.classList.add('flash');
  window.setTimeout(()=>t.classList.remove('flash'), 1400);
}
function citation(post, sources){
  const num=sourceNumber(post, sources), b=el('button','citation',String(num));
  b.type='button'; b.setAttribute('aria-label','View source '+num);
  b.addEventListener('click',()=>jumpToSource(post));
  return b;
}
function sourceExcerpt(p){ return shorten(p.summary||p.snippet||'Open the post to review the saved source.', 220); }
function folderBreakdown(sources){
  const counts=new Map();
  sources.forEach(p=>(p.folders||[]).forEach(f=>{ const n=folderName(f); counts.set(n,(counts.get(n)||0)+1); }));
  return [...counts.entries()].sort((a,b)=>b[1]-a[1]).slice(0,3).map(([n,c])=>n+' ('+c+')').join(', ');
}
function makeSourceCard(post, sources){
  const wrap=el('div','source-card'); wrap.id='source-'+sourceNumber(post, sources);
  const top=el('div','source-card-top');
  top.append(el('span','source-number',String(sourceNumber(post, sources))), el('span','source-folder', post.folders.length?folderName(post.folders[0]):'Saved'));
  wrap.append(top, el('div','source-author', post.author?'@'+post.author:'Saved post'), el('p','source-excerpt', sourceExcerpt(post)));
  const lrow=el('div','source-links');
  if(post.url){ const a=document.createElement('a'); a.href=post.url; a.target='_blank'; a.rel='noopener'; a.className='ig'; a.textContent='Instagram ↗'; lrow.append(a); }
  if(post.links&&post.links.length) lrow.append(el('span','linknote', post.links.length+' link'+(post.links.length>1?'s':'')+' discussed'));
  if(lrow.childNodes.length) wrap.append(lrow);
  wrap.addEventListener('click', e=>{ if(e.target.tagName!=='A') jumpToSource(post); });
  return wrap;
}
function sourcePanel(sources){
  const panel=el('aside','source-panel'); panel.setAttribute('aria-label','Sources used in this answer');
  const head=el('div','source-head'); head.append(el('h3','','Sources'), el('span','source-count',String(sources.length))); panel.append(head);
  const list=el('div','source-list'); sources.forEach(p=>list.append(makeSourceCard(p, sources))); panel.append(list);
  return panel;
}
function collectInsights(sources){
  const seen=new Set();
  const meta=/^(?:inferred role|content type|post type|format|topic|author type|creator role|media type|cultural|community|author|key quote|stated purpose|data of event|details|media pivots)(?:\s*(?:&|and)\s*[^:]*)?\s*:?\s*$/i;
  const metaLine=/^(?:inferred role|content type|post type|format|topic|author(?: type|\s*&\s*community breakdown)?|creator role|media type|community discussion(?: and discourse)?|key quote(?: from caption)?|stated purpose|data of event|details|media pivots)\s*:/i;
  const buckets=sources.map(post=>{
    let cands=(post.key_points||[]).slice();
    if(!cands.length && post.summary) cands=[post.summary];
    return cands.map(raw=>shorten(raw,280)).filter(text=>{
      const key=text.toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
      if(text.length<28 || /^#{1,3}/.test(text) || meta.test(text) || metaLine.test(text) || /^[^:]{2,50}:\s*$/.test(text) || seen.has(key)) return false;
      seen.add(key); return true;
    }).map(text=>({text, post}));
  });
  const out=[];
  for(let round=0; out.length<6 && round<12; round++)
    buckets.forEach(items=>{ if(items[round] && out.length<6) out.push(items[round]); });
  return out;
}
function relatedThemes(sources){
  const terms=new Set(state.q.toLowerCase().split(/\s+/).filter(Boolean)), counts=new Map(), first=new Map();
  sources.forEach(p=>(p.tags||[]).forEach(tag=>{
    const t=String(tag).toLowerCase();
    if(GENERIC_TAGS.has(t)||terms.has(t)||t.length<3) return;
    counts.set(t,(counts.get(t)||0)+1); if(!first.has(t)) first.set(t,p);
  }));
  return [...counts.entries()].sort((a,b)=>b[1]-a[1]).slice(0,4).map(([tag,count])=>({tag, count, post:first.get(tag)}));
}
function followups(sources){
  const wrap=el('div','followups');
  relatedThemes(sources).slice(0,3).forEach(({tag})=>{
    const b=el('button','followup','Explore '+tag); b.type='button';
    b.addEventListener('click',()=>{ document.getElementById('q').value=tag; state.q=tag; state.room=null; state.tag=null; renderRooms(); renderTags(); render(false); });
    wrap.append(b);
  });
  return wrap;
}
function buildKnowledgeView(matches){
  const host=document.getElementById('answers');
  host.replaceChildren();
  if(!state.q){ host.style.display='none'; return 0; }
  host.style.display='block';
  const deep=matches.filter(p=>p.has_knowledge), sources=deep.slice(0,8), folders=folderBreakdown(sources);
  const grounding=el('p','grounding'); grounding.append(el('span','grounding-dot'));
  if(sources.length) grounding.append(document.createTextNode('Built from '+sources.length+' deep-read '+(sources.length===1?'post':'posts')+(folders?' · '+folders:'')+(matches.length>sources.length?' · '+fmt(matches.length-sources.length)+' more matches':'')));
  else grounding.append(document.createTextNode(fmt(matches.length)+' catalog '+(matches.length===1?'match':'matches')+' · no deep-read content for this search'));
  host.append(grounding);
  if(!sources.length){
    const panel=el('section','limited-panel');
    panel.append(el('p','answer-kicker','Thin result'), el('h3','answer-title', matches.length?'No extracted knowledge yet':'Nothing in PIL covers this yet.'));
    panel.append(el('p','', matches.length?'Your saved posts match the words you searched, but none has a deeper extraction to support a knowledge answer. The matching posts are shown below.':'Try a broader search or remove a filter. The page won\u2019t fill gaps with outside knowledge.'));
    if(matches.length) panel.append(el('p','why-match','Why these posts: the terms appear in a creator name, caption, tag, folder, or extracted note.'));
    host.append(panel); return 0;
  }
  const grid=el('div','knowledge-grid');
  if(sources.length<3){
    const panel=el('section','limited-panel');
    panel.append(el('p','answer-kicker','Limited coverage'), el('h3','answer-title','Based on '+sources.length+' deep-read '+(sources.length===1?'post':'posts')), el('p','', 'There isn\u2019t enough coverage for a blended answer, so the source material stays attributed.'));
    sources.forEach(post=>{ const card=el('article','excerpt-card'); const h=el('h4','', post.author?'@'+post.author:'Saved post'); h.append(citation(post,sources)); card.append(h, el('p','',sourceExcerpt(post))); panel.append(card); });
    panel.append(el('p','why-match','Why these posts: your search terms appear in their captions, tags, folders, or extracted notes.'), followups(sources));
    grid.append(panel, sourcePanel(sources)); host.append(grid); return sources.length;
  }
  const answer=el('article','answer-panel');
  answer.append(el('p','answer-kicker','Answer from PIL'), el('h3','answer-title','What your saved posts say about \u201c'+state.q+'\u201d'));
  const lead=el('p','answer-lead');
  const themes=relatedThemes(sources), creators=new Set(sources.map(p=>p.author).filter(Boolean));
  lead.append(document.createTextNode('These '+sources.length+' deep-read matches come from '+creators.size+' '+(creators.size===1?'creator':'creators')+'. '));
  if(themes.length){
    lead.append(document.createTextNode('The most repeated tags are '));
    themes.slice(0,3).forEach((item,i)=>{ if(i) lead.append(document.createTextNode(i===Math.min(2,themes.length-1)?' and ':', ')); lead.append(document.createTextNode(item.tag), citation(item.post,sources)); });
    lead.append(document.createTextNode('. '));
  }
  lead.append(document.createTextNode('Open any citation to inspect the supporting post.'));
  answer.append(lead);
  const insights=collectInsights(sources);
  if(insights.length){
    const section=el('section','answer-section'); section.append(el('h3','','Key takeaways'));
    const list=el('ul','takeaways');
    insights.forEach(item=>{ const li=el('li',''); li.innerHTML=inlineMd(item.text); li.append(citation(item.post,sources)); list.append(li); });
    section.append(list); answer.append(section);
  }
  const howTo=/\b(how|make|build|recipe|steps?|setup|install|create)\b/i.test(state.q);
  const approaches=sources.filter(p=>clean(p.howto).length>35).slice(0,4);
  if(howTo && approaches.length>1){
    const section=el('section','answer-section'); section.append(el('h3','','Distinct approaches in your posts'));
    const list=el('div','approach-grid');
    approaches.forEach(post=>{ const box=el('article','approach'); const h=el('strong','', post.author?'@'+post.author:'Saved post'); h.append(citation(post,sources)); box.append(h, el('p','',shorten(post.howto,260))); list.append(box); });
    section.append(list); answer.append(section);
  }
  const f=followups(sources);
  if(f.childNodes.length){ const section=el('section','answer-section'); section.append(el('h3','','Keep exploring'), f); answer.append(section); }
  grid.append(answer, sourcePanel(sources)); host.append(grid);
  return sources.length;
}
function matches(p){
  if(state.room && !p.folders.includes(state.room)) return false;
  if(state.tag && !p.tags.includes(state.tag)) return false;
  return true;
}
function filtered(){
  const terms=state.q.toLowerCase().trim().split(/\s+/).filter(Boolean);
  let scored=[];
  for(const p of PIL.posts){
    if(!matches(p)) continue;
    const s=scorePost(p, terms);
    if(s<0) continue;
    scored.push({p, s});
  }
  scored.sort((a,b)=>{
    if(terms.length && b.s!==a.s) return b.s-a.s;
    return state.sort==='new' ? (b.p.saved_at||'').localeCompare(a.p.saved_at||'') : (a.p.saved_at||'').localeCompare(b.p.saved_at||'');
  });
  return scored.map(x=>x.p);
}
function cardHTML(p, i, featured){
  const color = PALETTE[i % PALETTE.length];
  const room = p.folders.length ? folderName(p.folders[0]) : 'Saved';
  const full = p.summary || p.snippet || 'Untitled post';
  const teaser = full.length > 280 ? full.slice(0, 280).trimEnd() + '…' : full;
  const headline = esc(teaser);
  const links = (p.links||[]).map(u=>'<li><a href="'+esc(u)+'" target="_blank" rel="noopener">'+esc(u)+'</a></li>').join('');
  const kps = (p.key_points||[]).map(k=>'<li>'+inlineMd(k)+'</li>').join('');
  const notes = (p.summary ? '<div class="sec"><span class="mono">Summary</span>'+md(p.summary)+'</div>' : '')
    + (p.key_points&&p.key_points.length ? '<div class="sec"><span class="mono">Key points</span><ul>'+kps+'</ul></div>':'')
    + (p.howto ? '<div class="sec"><span class="mono">How-to</span>'+md(p.howto)+'</div>':'')
    + (links ? '<div class="sec"><span class="mono">Links discussed</span><ul>'+links+'</ul></div>':'');
  return '<div class="card'+(featured?' featured':'')+'" id="card-'+p.id+'">'
    + '<div class="panel" style="background:'+color+'"><div class="prow"><span class="mono">'+esc(room)+'</span><span class="pnum">'+String(i+1).padStart(4,'0')+'</span></div><h3>'+headline+'</h3></div>'
    + '<div class="meta"><div class="kind mono">'+esc(p.media_type||'post')+'</div><div class="who">'+esc(p.author?'@'+p.author:'')+'</div>'
    + '<div class="rooms">'+p.folders.map(f=>esc(folderName(f))).join(' · ')+'</div>'
    + '<div class="foot"><button data-notes="'+p.id+'">Read notes</button><span>'+(p.links&&p.links.length?'<span class="ig">↗ '+p.links.length+' link'+(p.links.length>1?'s':'')+'</span> &nbsp;&nbsp;':'')+'<a class="ig" href="'+esc(p.url)+'" target="_blank" rel="noopener">Instagram ↗</a></span></div>'
    + (notes ? '<div class="notes" id="notes-'+p.id+'"><h4>Read notes</h4>'+notes+'</div>' : '')
    + '</div><span class="rdot"></span></div>';
}
function render(append){
  const list = filtered();
  if(!append) buildKnowledgeView(list);
  const feat = document.getElementById('featured'), grid = document.getElementById('grid');
  if(!append){ feat.innerHTML=''; grid.innerHTML=''; state.shown=0; }
  const slice = list.slice(state.shown, state.shown + __PAGE__);
  let htmlF='', htmlG='';
  slice.forEach((p,k)=>{ const idx=state.shown+k; const h=cardHTML(p,idx,idx===0&&state.shown===0); if(idx===0&&state.shown===0) htmlF=h; else htmlG+=h; });
  feat.innerHTML+=htmlF; grid.innerHTML+=htmlG;
  state.shown += slice.length;
  document.getElementById('count').textContent = list.length.toLocaleString()+' posts';
  document.getElementById('title').textContent = state.q ? 'Results for \u201c'+state.q+'\u201d' : 'Browse PIL';
  document.getElementById('empty').style.display = list.length ? 'none' : 'block';
  document.getElementById('more').style.display = state.shown < list.length ? '' : 'none';
  document.getElementById('more').textContent = 'SHOW MORE · '+(list.length-state.shown).toLocaleString()+' REMAINING';
  feat.querySelectorAll('[data-notes]').forEach(b=>b.onclick=()=>{const n=document.getElementById('notes-'+b.dataset.notes); if(n) n.classList.toggle('open');});
  grid.querySelectorAll('[data-notes]').forEach(b=>b.onclick=()=>{const n=document.getElementById('notes-'+b.dataset.notes); if(n) n.classList.toggle('open');});
}
function renderRooms(){
  const el = document.getElementById('rooms');
  let h = '<button class="room'+(state.room===null?' active':'')+'" data-room=""><span>'+(state.room===null?'<span class="dot"></span>':'')+'Everything</span><span class="n">'+PIL.posts.length.toLocaleString()+'</span></button>';
  PIL.folders.forEach(f=>{
    const c = PIL.posts.filter(p=>p.folders.includes(f.id)).length;
    h += '<button class="room'+(state.room===f.id?' active':'')+'" data-room="'+esc(f.id)+'"><span>'+(state.room===f.id?'<span class="dot"></span>':'')+esc(f.name)+'</span><span class="n">'+c.toLocaleString()+'</span></button>';
  });
  el.innerHTML=h;
  el.querySelectorAll('[data-room]').forEach(b=>b.onclick=()=>{state.room=b.dataset.room||null; renderRooms(); render(false);});
}
function renderTags(){
  const el=document.getElementById('tags');
  el.innerHTML = PIL.top_tags.map(t=>'<button class="chip'+(state.tag===t.tag?' active':'')+'" data-tag="'+esc(t.tag)+'">'+esc(t.tag)+' · '+t.n+'</button>').join('');
  el.querySelectorAll('[data-tag]').forEach(b=>b.onclick=()=>{state.tag = state.tag===b.dataset.tag?null:b.dataset.tag; renderTags(); render(false);});
}
let deb;
document.getElementById('q').addEventListener('input', e=>{clearTimeout(deb); deb=setTimeout(()=>{state.q=e.target.value.trim(); render(false);},220);});
document.addEventListener('keydown', e=>{ if(e.key==='/' && document.activeElement.tagName!=='INPUT'){ e.preventDefault(); document.getElementById('q').focus(); }});
document.getElementById('sort').addEventListener('change', e=>{state.sort=e.target.value; render(false);});
document.getElementById('more').addEventListener('click', ()=>render(true));
renderRooms(); renderTags(); render(false);
fetch('./phone.json').then(r=>r.ok?r.json():null).then(d=>{
  if(!d||!d.url) return;
  const panel=document.getElementById('phonepanel');
  document.getElementById('phonelink').href=d.url;
  document.getElementById('phonelink').textContent=d.url;
  const qr=document.getElementById('phoneqr');
  qr.src='./phone-qr.png';
  qr.onerror=()=>{qr.style.display='none';};
  panel.classList.add('show');
}).catch(()=>{});
</script>
__PWA_SW__
</body>
</html>
"""

SNIPPET_LEN = 280


PWA_HEAD = """<link rel="manifest" href="manifest.json">
<meta name="theme-color" content="#141414">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="PIL">
<link rel="apple-touch-icon" href="icon-180.png">"""

PWA_SW = """<script>
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function () {
    navigator.serviceWorker.register('sw.js').catch(function () {});
  });
}
</script>"""


def gather_data(db):
    """Read everything the dashboard needs. db must already be connected."""
    folders = [{"id": r["collection_id"], "name": r["name"]}
               for r in q(db, "SELECT collection_id, name, item_count FROM folders ORDER BY item_count DESC")]

    post_folders = {}
    for r in q(db, "SELECT post_id, collection_id FROM post_folders"):
        post_folders.setdefault(r["post_id"], []).append(r["collection_id"])

    tags = {}
    tag_counts = {}
    for r in q(db, "SELECT post_id, tag FROM tags"):
        tags.setdefault(r["post_id"], []).append(r["tag"])
        tag_counts[r["tag"]] = tag_counts.get(r["tag"], 0) + 1
    top_tags = [{"tag": t, "n": n} for t, n in sorted(tag_counts.items(), key=lambda x: -x[1])[:16]]

    knowledge = {}
    for r in q(db, "SELECT post_id, summary, key_points, howto, links FROM knowledge"):
        try:
            kp = json.loads(r["key_points"] or "[]")
        except Exception:
            kp = []
        try:
            links = json.loads(r["links"] or "[]")
        except Exception:
            links = []
        knowledge[r["post_id"]] = {
            "summary": (r["summary"] or "").strip(),
            "key_points": [s for s in kp if s][:8],
            "howto": (r["howto"] or "").strip()[:1200],
            "links": [u for u in links if u][:10],
        }

    posts = []
    for r in q(db, "SELECT post_id, url, author, media_type, caption, saved_at FROM posts"):
        cap = (r["caption"] or "").strip()
        snippet = cap[:SNIPPET_LEN] + ("…" if len(cap) > SNIPPET_LEN else "")
        p = {"id": r["post_id"], "url": r["url"] or "", "author": r["author"] or "",
             "media_type": (r["media_type"] or "post").lower(),
             "snippet": snippet, "tags": sorted(set(tags.get(r["post_id"], []))),
             "folders": sorted(set(post_folders.get(r["post_id"], []))),
             "saved_at": r["saved_at"] or ""}
        kn = knowledge.get(r["post_id"])
        if kn:
            p.update(kn)
        else:
            p.update({"summary": "", "key_points": [], "howto": "", "links": []})
        posts.append(p)

    posts_n = len(posts)
    stats = {
        "posts": posts_n,
        "summaries": sum(1 for p in posts if p["summary"]),
        "key_points": sum(len(p["key_points"]) for p in posts),
        "howtos": sum(1 for p in posts if p["howto"]),
        "link_posts": sum(1 for p in posts if p["links"]),
        "with_knowledge": sum(1 for p in posts if p["summary"] or p["key_points"] or p["howto"]),
        "rooms": len(folders),
    }
    return {"folders": folders, "top_tags": top_tags, "posts": posts, "stats": stats}


def render_page(d, pwa=False):
    """Build the dashboard HTML from gather_data() output."""
    folders, top_tags, posts, stats = d["folders"], d["top_tags"], d["posts"], d["stats"]
    data = {"folders": folders, "top_tags": top_tags, "posts": posts}
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    fmt = lambda n: f"{n:,}"
    page = (PAGE
            .replace("__TITLE__", html.escape(f"PIL — Personal Instagram Library ({fmt(stats['posts'])} posts)"))
            .replace("__POSTS__", fmt(stats["posts"]))
            .replace("__SUMMARIES__", fmt(stats["summaries"]))
            .replace("__KEYPOINTS__", fmt(stats["key_points"]))
            .replace("__HOWTOS__", fmt(stats["howtos"]))
            .replace("__LINKS__", fmt(stats["link_posts"]))
            .replace("__WITHKNOW__", fmt(stats["with_knowledge"]))
            .replace("__ROOMS__", fmt(stats["rooms"]))
            .replace("__PAGE__", str(PAGE_SIZE))
            .replace("__PALETTE__", json.dumps(PALETTE))
            .replace("__DATA__", payload)
            .replace("__PWA_HEAD__", PWA_HEAD if pwa else "")
            .replace("__PWA_SW__", PWA_SW if pwa else "")
            .replace("__FOOTER__", html.escape(
                f"Generated locally by PIL on {time.strftime('%Y-%m-%d')} · your data never left this machine")))
    for tok in ("__TITLE__", "__POSTS__", "__DATA__", "__PAGE__", "__PALETTE__",
                "__SUMMARIES__", "__KEYPOINTS__", "__HOWTOS__", "__LINKS__",
                "__WITHKNOW__", "__ROOMS__", "__FOOTER__",
                "__PWA_HEAD__", "__PWA_SW__"):
        assert tok not in page, tok
    return page


def main():
    cfg = load_config()
    out_path = (sys.argv[1] if len(sys.argv) > 1
                else os.path.join(os.path.expanduser(cfg["data_dir"]), "pil_library.html"))
    db = db_connect(cfg, read_only=True)
    d = gather_data(db)
    page = render_page(d)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)
    size = os.path.getsize(out_path)
    print(f"[done] {d['stats']['posts']} posts -> {out_path} ({size / 1024 / 1024:.1f} MB)", flush=True)
    db.close()


if __name__ == "__main__":
    main()
