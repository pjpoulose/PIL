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


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
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
.card .rdot{position:absolute;right:-2px;top:46%;width:7px;height:7px;background:#E0453A;border-radius:50%}
.more{text-align:center;margin-top:20px}
.more button{background:none;border:1px solid #2B2B2B;padding:14px 30px;font-family:ui-monospace,monospace;font-size:12px;letter-spacing:2px;color:#A39D8D;cursor:pointer}
.more button:hover{border-color:#E0453A;color:#EDE8DB}
.empty{padding:80px 0;text-align:center;color:#6E695D;font-family:Georgia,serif;font-style:italic;font-size:20px}
.footer-note{text-align:center;margin-top:70px;padding-top:26px;border-top:1px solid #242424;font-size:11px;letter-spacing:2.5px;color:#6E695D;text-transform:uppercase}
@media(max-width:900px){.body{flex-direction:column}.side{width:100%}.grid{grid-template-columns:1fr}.masthead h1{font-size:44px}.wrap{padding:0 24px 60px}}
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
const state = { q:'', room:null, tag:null, sort:'new', shown:__PAGE__ };
const folderName = id => (PIL.folders.find(f=>f.id===id)||{}).name || id;

function matches(p){
  if(state.room && !p.folders.includes(state.room)) return false;
  if(state.tag && !p.tags.includes(state.tag)) return false;
  if(state.q){
    const hay = [p.summary,p.snippet,p.author,(p.key_points||[]).join(' '),p.tags.join(' ')].join(' ').toLowerCase();
    if(!hay.includes(state.q.toLowerCase())) return false;
  }
  return true;
}
function filtered(){
  let r = PIL.posts.filter(matches);
  r.sort((a,b)=> state.sort==='new' ? (b.saved_at||'').localeCompare(a.saved_at||'') : (a.saved_at||'').localeCompare(b.saved_at||''));
  return r;
}
function cardHTML(p, i, featured){
  const color = PALETTE[i % PALETTE.length];
  const room = p.folders.length ? folderName(p.folders[0]) : 'Saved';
  const headline = esc(p.summary || p.snippet || 'Untitled post');
  const links = (p.links||[]).map(u=>'<li><a href="'+esc(u)+'" target="_blank" rel="noopener">'+esc(u)+'</a></li>').join('');
  const kps = (p.key_points||[]).map(k=>'<li>'+esc(k)+'</li>').join('');
  const notes = (p.key_points&&p.key_points.length ? '<div class="sec"><span class="mono">Key points</span><ul>'+kps+'</ul></div>':'')
    + (p.howto ? '<div class="sec"><span class="mono">How-to</span><p>'+esc(p.howto)+'</p></div>':'')
    + (links ? '<div class="sec"><span class="mono">Links discussed</span><ul>'+links+'</ul></div>':'');
  return '<div class="card'+(featured?' featured':'')+'">'
    + '<div class="panel" style="background:'+color+'"><div class="prow"><span class="mono">'+esc(room)+'</span><span class="pnum">'+String(i+1).padStart(4,'0')+'</span></div><h3>'+headline+'</h3></div>'
    + '<div class="meta"><div class="kind mono">'+esc(p.media_type||'post')+'</div><div class="who">'+esc(p.author?'@'+p.author:'')+'</div>'
    + '<div class="rooms">'+p.folders.map(f=>esc(folderName(f))).join(' · ')+'</div>'
    + '<div class="foot"><button data-notes="'+p.id+'">Read notes</button><span>'+(p.links&&p.links.length?'<span class="ig">↗ '+p.links.length+' link'+(p.links.length>1?'s':'')+'</span> &nbsp;&nbsp;':'')+'<a class="ig" href="'+esc(p.url)+'" target="_blank" rel="noopener">Instagram ↗</a></span></div>'
    + (notes ? '<div class="notes" id="notes-'+p.id+'"><h4>Read notes</h4>'+notes+'</div>' : '')
    + '</div><span class="rdot"></span></div>';
}
function render(append){
  const list = filtered();
  const feat = document.getElementById('featured'), grid = document.getElementById('grid');
  if(!append){ feat.innerHTML=''; grid.innerHTML=''; state.shown=0; }
  const slice = list.slice(state.shown, state.shown + __PAGE__);
  let htmlF='', htmlG='';
  slice.forEach((p,k)=>{ const idx=state.shown+k; const h=cardHTML(p,idx,idx===0&&state.shown===0); if(idx===0&&state.shown===0) htmlF=h; else htmlG+=h; });
  feat.innerHTML+=htmlF; grid.innerHTML+=htmlG;
  state.shown += slice.length;
  document.getElementById('count').textContent = list.length.toLocaleString()+' posts';
  document.getElementById('title').textContent = state.q ? 'Results for \\u201c'+state.q+'\\u201d' : 'Browse PIL';
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
</script>
</body>
</html>
"""

SNIPPET_LEN = 280


def main():
    cfg = load_config()
    out_path = (sys.argv[1] if len(sys.argv) > 1
                else os.path.join(os.path.expanduser(cfg["data_dir"]), "pil_library.html"))
    db = db_connect(cfg, read_only=True)

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

    n_posts = len(posts)
    n_summ = sum(1 for p in posts if p["summary"])
    n_kp = sum(len(p["key_points"]) for p in posts)
    n_how = sum(1 for p in posts if p["howto"])
    n_linkposts = sum(1 for p in posts if p["links"])
    n_know = sum(1 for p in posts if p["summary"] or p["key_points"] or p["howto"])

    data = {"folders": folders, "top_tags": top_tags, "posts": posts}
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    fmt = lambda n: f"{n:,}"
    page = (PAGE
            .replace("__TITLE__", html.escape(f"PIL — Personal Instagram Library ({fmt(n_posts)} posts)"))
            .replace("__POSTS__", fmt(n_posts))
            .replace("__SUMMARIES__", fmt(n_summ))
            .replace("__KEYPOINTS__", fmt(n_kp))
            .replace("__HOWTOS__", fmt(n_how))
            .replace("__LINKS__", fmt(n_linkposts))
            .replace("__WITHKNOW__", fmt(n_know))
            .replace("__ROOMS__", fmt(len(folders)))
            .replace("__PAGE__", str(PAGE_SIZE))
            .replace("__PALETTE__", json.dumps(PALETTE))
            .replace("__DATA__", payload)
            .replace("__FOOTER__", html.escape(
                f"Generated locally by PIL on {time.strftime('%Y-%m-%d')} · your data never left this machine")))
    # sanity: no unreplaced tokens remain
    assert "__" not in page.replace("__", "\x00", 0) or True
    for tok in ("__TITLE__", "__POSTS__", "__DATA__", "__PAGE__", "__PALETTE__",
                "__SUMMARIES__", "__KEYPOINTS__", "__HOWTOS__", "__LINKS__",
                "__WITHKNOW__", "__ROOMS__", "__FOOTER__"):
        assert tok not in page, tok

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)
    size = os.path.getsize(out_path)
    print(f"[done] {n_posts} posts -> {out_path} ({size / 1024 / 1024:.1f} MB)", flush=True)
    db.close()


if __name__ == "__main__":
    main()
