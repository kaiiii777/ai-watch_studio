#!/usr/bin/env python3
from __future__ import annotations

import base64, hashlib, hmac, json, mimetypes, os, pathlib, queue, re, secrets, shutil, subprocess, tempfile, time, uuid, threading
import urllib.error, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "data"
UPLOADS = DATA / "uploads"
HISTORY = DATA / "generation_history.jsonl"
PROMPT_FAVORITES = DATA / "prompt_favorites.json"
KEYS = DATA / "api_keys.json"
LOGIN_CONFIG = DATA / "login.json"
LOGIN_SESSIONS = {}
LOGIN_ATTEMPTS = {}
LOGIN_LOCK = threading.Lock()
LOGIN_TTL = 7 * 24 * 60 * 60
HOST = os.environ.get("IMAGE_APP_HOST", "127.0.0.1")
PORT = int(os.environ.get("IMAGE_APP_PORT", "8900"))
AUTH_ENABLED = os.environ.get("IMAGE_AUTH_ENABLED", "0").strip().lower() in ("1", "true", "yes")
API_BASE = os.environ.get("IMAGE_API_BASE", "https://www.hfsyapi.cn").rstrip("/")
IMAGE_UPSTREAMS = {"hfsy": API_BASE, "tyai": "https://tyaiapi.com"}
IMAGE_UPSTREAM_CONFIG = DATA / 'image_upstream.json'
ANALYSIS_API_BASE = os.environ.get("ANALYSIS_API_BASE", "https://www.owlai.top").rstrip("/")
ANALYSIS_UPSTREAMS = {
    "owlai": ANALYSIS_API_BASE,
    "tyai": "https://tyaiapi.com",
}
PUBLIC_UPLOAD_BASE = os.environ.get("IMAGE_PUBLIC_UPLOAD_BASE", "").rstrip("/")
REMOTE_UPLOAD_HOST = os.environ.get("IMAGE_REMOTE_UPLOAD_HOST", "").strip()
REMOTE_UPLOAD_USER = os.environ.get("IMAGE_REMOTE_UPLOAD_USER", "ubuntu").strip()
REMOTE_UPLOAD_KEY = os.environ.get("IMAGE_REMOTE_UPLOAD_KEY", "").strip()
REMOTE_UPLOAD_DIR = os.environ.get("IMAGE_REMOTE_UPLOAD_DIR", "").strip()
PUBLIC_UPLOAD_API_BASE = os.environ.get("IMAGE_PUBLIC_UPLOAD_API_BASE", "").rstrip("/")
PUBLIC_UPLOAD_TOKEN = os.environ.get("IMAGE_PUBLIC_UPLOAD_TOKEN", "").strip()
PUBLIC_UPLOAD_CONFIG = DATA / 'public_upload.json'
MAX_UPLOAD = 120 * 1024 * 1024
OUTPUTS = DATA / "outputs"
REFERENCE_CACHE = DATA / "reference_cache"
REFERENCE_THUMB_LOCK = threading.Lock()
FILE_LOCK = threading.Lock()
IMAGE_WARM_LOCK = threading.Lock()
WARMED_IMAGE_URLS = {}
WARMING_IMAGE_URLS = {}
IMAGE_WARM_FAILURES = {}
ANALYSIS_BATCH_LOCK = threading.Lock()
ANALYSIS_BATCHES = {}

HTML = r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Watch Studio · 分析与生图</title>
<style>
.workspace{display:block!important}.shell{max-width:980px!important}.sidebar{position:static!important;margin-bottom:18px}.hero{display:none!important}.thumbs{grid-template-columns:repeat(7,1fr)}
.history-item p{white-space:normal!important;overflow-wrap:anywhere;line-height:1.55;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;overflow:hidden}
:root{font-family:Inter,-apple-system,BlinkMacSystemFont,"PingFang SC","Segoe UI",sans-serif;color:#17202f;background:#f4f6f8;--ink:#17202f;--muted:#718096;--line:#e4e8ee;--blue:#2457f5;--soft:#eef3ff;--green:#1a9c68;--red:#d14a55}*{box-sizing:border-box}body{margin:0}button,input,textarea,select{font:inherit}button{border:0;cursor:pointer}.app{min-height:100vh}.topbar{height:72px;border-bottom:1px solid var(--line);background:rgba(255,255,255,.9);display:flex;align-items:center;justify-content:space-between;padding:0 36px;position:sticky;top:0;z-index:5;backdrop-filter:blur(12px)}.brand{display:flex;gap:12px;align-items:center}.brand-mark{width:34px;height:34px;border-radius:11px;background:linear-gradient(135deg,#224af1,#6d87ff);color:#fff;display:grid;place-items:center;font-weight:800}.brand h1{font-size:17px;margin:0}.brand p{font-size:11px;color:var(--muted);margin:3px 0 0}.top-actions{display:flex;gap:10px;align-items:center}.shell{max-width:1420px;margin:0 auto;padding:28px 36px 60px}.workspace{display:grid;grid-template-columns:360px minmax(0,1fr);gap:24px;align-items:start}.panel{background:#fff;border:1px solid var(--line);border-radius:18px;box-shadow:0 8px 30px rgba(26,39,68,.04)}.sidebar{padding:22px;position:sticky;top:96px}.content{min-width:0}.section-title{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px}.section-title h2{font-size:15px;margin:0}.section-title p{font-size:12px;color:var(--muted);margin:5px 0 0;line-height:1.5}.field{margin:16px 0}.field label{display:flex;justify-content:space-between;font-size:12px;font-weight:700;margin-bottom:8px;color:#526074}.field label span{font-weight:500;color:var(--muted)}input,textarea,select{width:100%;border:1px solid #dfe4ec;border-radius:10px;padding:10px 12px;background:#fff;color:var(--ink);outline:none}input:focus,textarea:focus,select:focus{border-color:#7b96ff;box-shadow:0 0 0 3px #eef2ff}textarea{resize:vertical;min-height:88px;line-height:1.55}.model-row{display:grid;grid-template-columns:1fr 1fr;gap:8px}.dropzone{border:1px dashed #bdc8da;background:#fafbfe;border-radius:13px;padding:17px;text-align:center;cursor:pointer}.dropzone:hover{border-color:var(--blue);background:#f7f9ff}.dropzone input{display:none}.dropzone strong{font-size:13px}.dropzone small{display:block;color:var(--muted);font-size:11px;margin-top:6px}.thumbs{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin-top:10px}.thumb{position:relative}.thumb img{width:100%;aspect-ratio:1;object-fit:cover;border-radius:8px;border:1px solid var(--line)}.thumb em{position:absolute;left:4px;top:4px;font-style:normal;font-size:10px;background:var(--ink);color:white;border-radius:4px;padding:2px 4px}.thumb button{position:absolute;right:3px;top:3px;width:18px;height:18px;border-radius:50%;background:#fff;color:#555;font-size:12px}.primary{background:var(--blue);color:#fff;border-radius:10px;padding:11px 15px;font-weight:700}.primary:hover{background:#1744df}.secondary{background:#f1f4f8;color:#344054;border-radius:9px;padding:9px 12px;font-weight:600}.ghost{background:transparent;color:var(--muted);padding:6px}.full{width:100%}.split{display:grid;grid-template-columns:1fr 1fr;gap:10px}.note{font-size:11px;color:var(--muted);line-height:1.5}.hero{padding:27px 30px;background:linear-gradient(135deg,#fff 0%,#f5f7ff 100%);border:1px solid var(--line);border-radius:18px;margin-bottom:18px}.eyebrow{font-size:11px;letter-spacing:.12em;color:var(--blue);font-weight:800;text-transform:uppercase}.hero h2{font-size:28px;line-height:1.2;margin:8px 0 7px;letter-spacing:-.03em}.hero p{margin:0;color:var(--muted);font-size:13px}.toolbar{display:flex;justify-content:space-between;align-items:center;margin:0 0 12px}.toolbar h2{font-size:16px;margin:0}.toolbar-right{display:flex;gap:8px}.analysis-card{padding:20px;margin-bottom:18px}.analysis-grid{display:grid;grid-template-columns:260px minmax(0,1fr);gap:20px}.selling{background:#f7f9fc;border-radius:12px;padding:14px}.selling h3{font-size:12px;margin:0 0 10px}.selling ul{padding-left:18px;margin:0;color:#526074;font-size:12px;line-height:1.8}.prompts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.prompt-card{border:1px solid var(--line);border-radius:13px;padding:13px;background:#fff}.prompt-card header{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:9px}.prompt-card header strong{font-size:12px}.badge{font-size:10px;color:var(--blue);background:var(--soft);border-radius:99px;padding:3px 7px}.prompt-card textarea{min-height:112px;font-size:12px}.prompt-actions{display:flex;justify-content:flex-end;margin-top:8px}.results{padding:20px;margin-bottom:18px}.result-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.result-card{border:1px solid var(--line);border-radius:14px;overflow:hidden;background:#fff}.result-media{aspect-ratio:1;background:#f3f5f8;display:grid;place-items:center;color:var(--muted);font-size:12px;position:relative}.result-media img{width:100%;height:100%;object-fit:cover}.result-media.error{color:var(--red);background:#fff7f7}.result-meta{padding:11px 12px}.result-meta strong{font-size:12px;display:block}.result-meta small{color:var(--muted);font-size:11px;display:block;margin-top:3px}.result-actions{display:flex;gap:7px;margin-top:10px}.result-actions button{flex:1;padding:7px 8px;font-size:11px;border-radius:7px}.logs{padding:18px}.logs summary{cursor:pointer;font-size:13px;font-weight:700}.logbox{height:170px;overflow:auto;background:#121827;color:#cbd5e1;border-radius:10px;margin-top:12px;padding:12px;font:11px/1.65 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre-wrap}.history{padding:20px}.history-list{display:grid;gap:10px}.history-item{border:1px solid var(--line);border-radius:12px;padding:12px;display:grid;grid-template-columns:72px 1fr auto;gap:12px;align-items:center}.history-item img{width:72px;height:72px;object-fit:cover;border-radius:8px;background:#f3f5f8}.history-item strong{font-size:12px}.history-item p{font-size:11px;color:var(--muted);margin:5px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.empty{text-align:center;padding:28px;color:var(--muted);font-size:12px}.status{font-size:11px;color:var(--muted)}.status.ok{color:var(--green)}.status.bad{color:var(--red)}.hidden{display:none!important}@media(max-width:1050px){.workspace{grid-template-columns:1fr}.sidebar{position:static}.analysis-grid{grid-template-columns:1fr}.result-grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:650px){.topbar{padding:0 16px}.shell{padding:18px 14px 40px}.top-actions .secondary{display:none}.prompts,.result-grid{grid-template-columns:1fr}.hero{padding:22px}.hero h2{font-size:23px}.history-item{grid-template-columns:56px 1fr}.history-item img{width:56px;height:56px}.history-item .secondary{grid-column:2}}
.thumb{cursor:grab;user-select:none;-webkit-user-select:none}.thumb:active{cursor:grabbing}.thumb img{pointer-events:none}.thumb.dragging{opacity:.45;transform:scale(.94);transition:transform .12s ease,opacity .12s ease}.thumb.drop-before::before,.thumb.drop-after::after{content:'';position:absolute;left:4px;right:4px;height:3px;border-radius:3px;background:var(--blue);z-index:3;box-shadow:0 0 0 1px #fff}.thumb.drop-before::before{top:-4px}.thumb.drop-after::after{bottom:-4px}.thumbs-bar{display:flex;align-items:center;justify-content:space-between;margin-top:9px;gap:8px}.thumbs-bar span{font-size:11px;color:var(--muted)}.thumbs-bar .secondary{padding:3px 10px;font-size:11px;border-radius:8px}
</style></head><body><div class="app"><header class="topbar"><div class="brand"><div class="brand-mark">W</div><div><h1>Watch Studio</h1><p>商品视觉分析与生图工作台</p></div></div><div class="top-actions"><button class="secondary" id="historyBtn">最近任务</button><button class="secondary" id="keyBtn">API Key 配置</button></div></header>
<main class="shell"><div class="workspace"><aside class="panel sidebar"><div class="section-title"><div><h2>生成配置</h2><p>上传参考图后，由 GPT-5.4 完成卖点分析。</p></div></div><div class="field"><label>生成模式</label><select id="mode"><option value="analyze" selected>思考并生成详情图</option><option value="prompt">按提示词直接生成</option></select></div><div class="field"><label>生图模型</label><select id="model"><option value="gpt-image-2">gpt-image-2</option><option value="nano-banana-2">nano-banana-2</option></select></div><div class="field"><label>分析模型</label><select id="analyzeModel"><option value="gpt-5.4" selected>gpt-5.4</option><option value="gpt-5.6-terra">gpt-5.6-terra</option></select></div><div class="field"><label>参考图片 <span id="refsHint">第一张为产品主体</span></label><label class="dropzone"><input id="files" type="file" accept="image/*" multiple><strong>点击或拖入图片</strong><small>支持多张，其余用于细节/风格参考；拖拽缩略图可调整顺序，第一张为产品主体</small></label><div id="thumbs" class="thumbs"></div><div class="thumbs-bar hidden" id="thumbsBar"><span id="thumbsCount"></span><button type="button" class="secondary" id="clearThumbs">清空全部</button></div></div><div class="field"><label>总体要求 <span>可选</span></label><textarea id="userPrompt" placeholder="例如：突出夜光、商务通勤场景，整体偏深蓝高级感"></textarea></div><div class="split"><div class="field"><label>比例</label><select id="aspect"><option selected>1:1</option><option>4:5</option><option>3:4</option><option>16:9</option><option>9:16</option><option>4:3</option></select></div><div class="field"><label>出图数量</label><select id="count"><option selected>6</option><option>1</option><option>2</option><option>3</option><option>4</option><option>5</option></select></div></div><button class="primary full" id="run">分析并生成</button><p class="note" style="margin-bottom:0">分析会生成卖点和对应提示词。你可以先编辑某一张提示词，再单独重新生成。</p><div class="field hidden" id="keyPanel"><label>HFSY API Key</label><input id="apiKey" type="password" placeholder="sk-..."><div class="split" style="margin-top:8px"><button class="secondary" id="saveKey">保存</button><button class="secondary" id="clearKey">清除</button></div></div></aside><section class="content"><div class="hero"><div class="eyebrow">Product image intelligence</div><h2>把一张手表图，变成一整套详情页视觉。</h2><p>先理解产品卖点，再用统一的产品身份、配色和风格生成多张可编辑的商品图。</p></div><div id="analysis" class="panel analysis-card hidden"><div class="section-title"><div><h2>卖点分析 & 提示词</h2><p>分析结果可直接修改，修改后点击对应卡片的“重新生成”。</p></div><span class="status" id="analysisStatus"></span></div><div class="analysis-grid"><div class="selling"><h3>核心卖点</h3><ul id="selling"></ul></div><div id="prompts" class="prompts"></div></div></div><div class="panel results"><div class="toolbar"><div><h2>生成结果</h2><span class="status" id="resultStatus">等待开始</span></div><div class="toolbar-right"><button class="secondary" id="export">一键导出</button><button class="secondary" id="refresh">刷新任务</button></div></div><div id="resultGrid" class="result-grid"><div class="empty">上传参考图并点击“分析并生成”</div></div></div><details class="panel logs"><summary>运行日志</summary><div class="logbox" id="logs"></div></details><div class="panel history" id="history"><div class="toolbar"><h2>最近任务</h2><button class="ghost" id="reloadHistory">刷新</button></div><div id="historyList" class="history-list"><div class="empty">暂无保存记录</div></div></div></section></div></main></div>
<script>
const $=id=>document.getElementById(id);let refs=[],current=null,history=[],generationToken=0;const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function log(x){const line=`[${new Date().toLocaleTimeString()}] ${typeof x==='string'?x:JSON.stringify(x)}`;$('logs').textContent+=line+'\n';$('logs').scrollTop=$('logs').scrollHeight}
function readFile(file){return new Promise((res,rej)=>{const r=new FileReader();r.onload=()=>res(r.result);r.onerror=rej;r.readAsDataURL(file)})}
function beginReuseEdit(){if(current?._watchLoaded)current._watchLoaded=false}
function referencePreviewUrl(url,thumb=true){return '/api/reference-image?'+(thumb?'thumb=1&':'')+'url='+encodeURIComponent(url)}
function renderThumbs(){ $('thumbs').innerHTML=refs.map((x,i)=>`<div class="thumb" draggable="true" data-i="${i}"><img src="${x.remote?referencePreviewUrl(x.url):x.preview}" data-full="${esc(x.remote?referencePreviewUrl(x.url,false):(x.url||x.preview))}" loading="lazy" decoding="async" draggable="false"><em>${labelFor(i)}</em><button data-i="${i}">×</button></div>`).join('');const box=$('thumbs');box.querySelectorAll('.thumb').forEach(el=>{el.ondragstart=dragStart;el.ondragover=dragOver;el.ondragleave=dragLeave;el.ondrop=dragDrop;el.ondragend=dragEnd});box.querySelectorAll('button').forEach(b=>b.onclick=()=>{beginReuseEdit();refs.splice(+b.dataset.i,1);renderThumbs()}) ;const tb=$('thumbsBar');if(tb){tb.classList.toggle('hidden',!refs.length);const tc=$('thumbsCount');if(tc)tc.textContent=refs.length+'/7 张'} }
let dragFrom=null,dragTo=null;
function dragMark(el,after){if(dragTo&&dragTo!==el){dragTo.classList.remove('drop-before','drop-after')}dragTo=el;el.classList.toggle('drop-before',!after);el.classList.toggle('drop-after',after)}
function dragStart(e){dragFrom=+e.currentTarget.dataset.i;e.currentTarget.classList.add('dragging');e.dataTransfer.effectAllowed='move';try{e.dataTransfer.setData('text/plain','1')}catch(_){}}
function dragOver(e){if(dragFrom==null)return;e.preventDefault();e.dataTransfer.dropEffect='move';const el=e.currentTarget,r=el.getBoundingClientRect();dragMark(el,e.clientY>r.top+r.height/2)}
function dragLeave(e){const el=e.currentTarget;if(e.relatedTarget&&el.contains(e.relatedTarget))return;el.classList.remove('drop-before','drop-after');if(dragTo===el)dragTo=null}
function dragDrop(e){e.preventDefault();const el=e.currentTarget;if(dragFrom==null)return;const from=dragFrom,to=+el.dataset.i,r=el.getBoundingClientRect(),after=e.clientY>r.top+r.height/2;dragEnd();if(from===to)return;beginReuseEdit();const [item]=refs.splice(from,1);refs.splice((from<to?to-1:to)+(after?1:0),0,item);renderThumbs()}
function dragEnd(){const d=$('thumbs').querySelector('.thumb.dragging');if(d)d.classList.remove('dragging');if(dragTo){dragTo.classList.remove('drop-before','drop-after');dragTo=null}dragFrom=null}
$('files').onchange=async e=>{const picked=[...e.target.files];if(picked.length)beginReuseEdit();let added=0;for(const f of picked){if(refs.length>=7)break;const dup=refs.some(x=>x.file.name===f.name&&x.file.size===f.size&&x.file.lastModified===f.lastModified);if(dup)continue;refs.push({file:f,preview:URL.createObjectURL(f)});added++}if(added<picked.length)log(added?'部分图片未添加：最多 7 张或存在重复':'未添加新图：最多 7 张或已存在重复');e.target.value='';renderThumbs()};
async function api(path,body,method='POST'){const r=await fetch(path,{method,headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});const t=await r.text();let j={};try{j=t?JSON.parse(t):{}}catch{j={raw:t}}if(!r.ok)throw Error(JSON.stringify(j));return j}
function blobDataUrl(blob){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(blob)})}
async function uploadAll(){const out=[];for(const x of refs){if(x.url&&/^https?:\/\//.test(x.url)){out.push(x.url);continue}const dataUrl=x.file?await readFile(x.file):x.url?await fetch(x.url).then(r=>{if(!r.ok)throw Error('无法读取历史参考图');return r.blob()}).then(blobDataUrl):null;if(!dataUrl)throw Error('缺少参考图文件');const filename=x.file?.name||x.name||'reference-image.png';const contentType=x.file?.type||dataUrl.match(/^data:([^;,]+)/)?.[1]||'image/png';const j=await api('/api/upload',{filename,contentType,dataUrl});x.url=j.url;out.push(j.url)}return out}
function promptText(p){return p.prompt||p.description||''}
function renderAnalysis(){if(!current)return;$('analysis').classList.remove('hidden');$('selling').innerHTML=(current.selling_points_cn||[]).map(x=>`<li>${esc(x)}</li>`).join('');$('prompts').innerHTML=current.prompts.map((p,i)=>`<article class="prompt-card"><header><strong>${i+1}. ${esc(p.title||'详情图')}</strong><span class="badge">${esc(p.purpose||'商品详情')}</span></header><textarea data-prompt="${i}">${esc(promptText(p))}</textarea><div class="prompt-actions"><button class="secondary regen" data-i="${i}">重新生成</button></div></article>`).join('');$('prompts').querySelectorAll('textarea').forEach(t=>t.oninput=()=>current.prompts[+t.dataset.prompt].prompt=t.value);$('prompts').querySelectorAll('.regen').forEach(b=>b.onclick=()=>regen(+b.dataset.i))}
function renderResults(){const items=current?.results||[];$('resultGrid').innerHTML=items.length?items.map((x,i)=>`<article class="result-card"><div class="result-media ${x.status==='error'?'error':''}">${x.url?`<img src="${esc(x.url)}">`:(x.status==='error'?`生成失败<br>${esc(x.error||'请重新生成')}`:'生成中…')}</div><div class="result-meta"><strong>${i+1}. ${esc(current.prompts[i]?.title||'详情图')}</strong><small>${x.status==='success'?'已完成':x.status==='error'?'失败':'处理中'}</small><div class="result-actions"><button class="secondary regen" data-i="${i}">重新生成</button>${x.url?`<button class="secondary save" data-i="${i}">保存图片</button>`:''}</div></div></article>`).join(''):'<div class="empty">上传参考图并点击“分析并生成”</div>';$('resultGrid').querySelectorAll('.regen').forEach(b=>b.onclick=()=>regen(+b.dataset.i));$('resultGrid').querySelectorAll('.save').forEach(b=>b.onclick=()=>saveOne(+b.dataset.i))}
function sizeFor(a){return ({'1:1':'1024x1024','4:5':'832x1040','3:4':'768x1024','16:9':'1280x720','9:16':'720x1280','4:3':'1024x768'})[a]||'1024x1024'}
function createBody(prompt,images,model=$('model').value,aspect=$('aspect').value){if(model==='nano-banana-2'||model==='gemini-3.1-flash-image-preview')return{endpoint:`/v1beta/models/${model}:generateContent`,model,contents:[{parts:[{text:prompt},...images.map(url=>({fileData:{mimeType:'image/jpeg',fileUri:url}}))]}],generationConfig:{imageConfig:{aspectRatio:aspect}},async:true,background:true};return{endpoint:'/v1/images/generations',model,prompt,size:sizeFor(aspect),reference_images:images,n:1,response_format:'b64_json',async:true,background:true}}
async function run(){if(!refs.length)throw Error('请先上传至少 1 张参考图');const token=++generationToken;current=null;$('analysis').classList.add('hidden');renderResults();$('run').disabled=true;$('resultStatus').textContent='正在上传参考图…';try{const images=await uploadAll();const mode=$('mode').value;if(mode==='prompt'){const prompt=$('userPrompt').value.trim();if(!prompt)throw Error('请输入总体要求/提示词');current={generationId:'p-'+Date.now().toString(36)+Math.random().toString(36).slice(2,7),images,model:$('model').value,aspect:$('aspect').value,userPrompt:prompt,mode:'prompt',prompts:[],results:[]};$('resultStatus').textContent='按提示词直接生成中…';await generatePromptAll(token)}else{$('resultStatus').textContent='GPT-5.4 分析中…';const a=await api('/api/analyze',{images,userPrompt:$('userPrompt').value.trim(),count:+$('count').value,model:$('model').value,aspect:$('aspect').value,analyzeModel:$('analyzeModel').value});if(token!==generationToken)return;current={...a,images,model:$('model').value,aspect:$('aspect').value,token,results:a.prompts.map(()=>({status:'creating',url:''}))};renderAnalysis();renderResults();$('resultStatus').textContent='分析完成，正在提交 '+(a.prompts.length||count)+' 张图片…';await generateAll(token)}}catch(e){log(e.message);$('resultStatus').textContent='执行失败'}finally{if(token===generationToken)$('run').disabled=false}}
async function generatePromptAll(token){const prompt=$('userPrompt').value.trim();const count=+$('count').value;for(let i=0;i<count;i++){const title=prompt.length>24?prompt.slice(0,24)+'…':prompt;current.prompts.push({title,purpose:'按提示词',prompt});current.results.push({status:'creating',url:''})}renderResults();await saveHistory();$('resultStatus').textContent=`正在生成 ${count} 张…`;for(let i=0;i<count;i++){if(token!==generationToken)return;try{await generateOne(i+1,prompt)}catch(_){}}if(token!==generationToken)return;await saveHistory();loadHistory();$('resultStatus').textContent=current.results.every(x=>x.url)?'本轮生成完成':'部分图片生成失败'}
function labelFor(i){if($('mode').value==='prompt')return i===0?'图 1':`图 ${i+1}`;return i===0?'主体':`参考 ${i}`}
function refreshModeUI(){$('run').textContent=$('mode').value==='prompt'?'直接生成':'分析并生成';const sm=document.querySelector('.dropzone small');if(sm)sm.textContent=$('mode').value==='prompt'?'按提示词直接生成；上传图片作为参考，第一张作为主要参考':'支持多张，其余用于细节/风格参考；拖拽缩略图可调整顺序，第一张为产品主体';const rh=$('refsHint');if(rh)rh.textContent=$('mode').value==='prompt'?'可拖拽排序，第一张作为主要参考':'第一张为产品主体';renderThumbs()}
async function generateAll(token){const total=current.prompts.length;$('resultStatus').textContent=`已并发提交 ${total} 张，正在分别生成…`;const jobs=current.prompts.map((p,i)=>token===generationToken?generateOne(i+1,promptText(p),token).catch(()=>{}):Promise.resolve());await Promise.all(jobs);if(token!==generationToken)return;await saveHistory();loadHistory();$('resultStatus').textContent=current.results.every(x=>x.status==='success')?'本轮生成完成':current.results.some(x=>x.status==='success')?'部分图片生成完成':'本轮生成失败'}
function resultRevision(){return String(BigInt(Date.now())*1000000n)}
function ensureResultVersions(slot){if(!slot)return[];if(!Array.isArray(slot.versions))slot.versions=[];slot.versions=slot.versions.filter(item=>item&&item.url);if(slot.url&&!slot.versions.length)slot.versions.push({url:slot.url,updatedAt:slot.updatedAt||resultRevision(),label:'原始版本'});if(slot.versions.length&&slot.activeVersion==null){const found=slot.versions.map(item=>item.url).lastIndexOf(slot.url);slot.activeVersion=found>=0?found:slot.versions.length-1}return slot.versions}
function commitGeneratedResult(job,index,response){const old=job.results[index]||{};const versions=ensureResultVersions(old).slice();const oldUrl=old.url||'';if(response.previousUrl){const oldIndex=oldUrl?versions.findIndex(item=>item.url===oldUrl):-1;if(oldIndex>=0)versions[oldIndex]={...versions[oldIndex],url:response.previousUrl};else if(!versions.some(item=>item.url===response.previousUrl))versions.push({url:response.previousUrl,updatedAt:old.updatedAt||String(Date.now()),label:'之前版本'})}const updatedAt=response.updatedAt||String(Date.now());versions.push({url:response.url,updatedAt,sourceUrl:response.sourceUrl||'',label:'当前版本',direction:job.prompts[index]?.regenDirection||''});job.results[index]={...old,status:'success',url:response.url,sourceUrl:response.sourceUrl||'',previousUrl:'',taskId:response.taskId||response.id||old.taskId||'',updatedAt,versions,activeVersion:versions.length-1,error:''}}
async function generateOne(i,prompt,token=generationToken,job=current){if(!job?.generationId||token!==generationToken)return;const j=i-1;const prior=job.results[j]||{};ensureResultVersions(prior);job.results[j]={...prior,status:'creating',url:prior.url||'',error:'',updatedAt:resultRevision()};if(current===job)renderResults();try{const r=await api('/api/create',{...createBody(prompt,job.images,job.model,job.aspect),index:i,generationId:job.generationId,model:job.model,userPrompt:job.userPrompt||'',aspect:job.aspect,title:job.prompts[j]?.title||''});if(token!==generationToken)return;job.results[j].taskId=r.taskId||r.id||'';if(r.url){commitGeneratedResult(job,j,r)}else if(job.results[j].taskId){await poll(i,token,job)}else throw Error('接口未返回图片或任务 ID')}catch(e){if(token===generationToken){const failed=job.results[j]||{};job.results[j]={...failed,status:'error',url:failed.url||'',error:e.message,updatedAt:resultRevision()};log(`第 ${i} 张失败：${e.message}`)}}if(current===job)renderResults()}
async function poll(i,token,job=current){const deadline=Date.now()+150000;let attempt=0;while(Date.now()<deadline&&token===generationToken){await new Promise(r=>setTimeout(r,5000));attempt++;const x=job.results[i-1];try{const r=await api('/api/query',{taskId:x.taskId,model:job.model,generationId:job.generationId,index:i});log(`第 ${i} 张查询第 ${attempt} 次`);if(token!==generationToken)return;if(r.url){commitGeneratedResult(job,i-1,r);return}if(r.status&&['failed','error','failure'].includes(r.status)){x.status='error';x.error=r.error||r.status;return}}catch(e){log(`第 ${i} 张查询暂时失败：${e.message}`)}}if(token===generationToken){const failed=job.results[i-1]||{};job.results[i-1]={...failed,status:'error',url:failed.url||'',error:'等待 150 秒仍未返回结果'}}}
async function ensurePublicReferences(job=current){const images=job?.images||[];if(!images.length)throw Error('缺少参考图，请重新载入任务或上传图片');if(images.every(url=>/^https?:\/\//.test(String(url))))return images;if(job!==current)throw Error('原任务参考图尚未上传完成，请重新载入后再试');job.images=await uploadAll();if(job.images.some(url=>!/^https?:\/\//.test(String(url))))throw Error('参考图尚未上传到公网服务器，请重新载入任务后再试');return job.images}
async function regen(i){const job=current;if(!job?.generationId)throw Error('未找到当前任务，无法覆盖原图片');const t=document.querySelector(`textarea[data-prompt="${i}"]`);if(t)job.prompts[i].prompt=t.value;const old=job.results[i]||{};ensureResultVersions(old);job.results[i]={...old,status:'creating',url:old.url||'',error:'',updatedAt:resultRevision()};job.status='generating';if(current===job){$('resultStatus').textContent='正在上传参考图…';renderResults()}await saveHistory(job);await ensurePublicReferences(job);if(current===job)$('resultStatus').textContent=`正在重新生成第 ${i+1} 张…`;await generateOne(i+1,promptText(job.prompts[i]),generationToken,job);await saveHistory(job);loadHistory()}
async function saveOne(i){const image=document.querySelectorAll('#resultGrid .result-card .result-media img')[i];const url=image?.currentSrc||image?.getAttribute('src')||current?.results?.[i]?.url;if(!url)throw Error(`第 ${i+1} 张图片尚未生成`);const blob=await fetchBlob(url);const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`watch-detail-${i+1}.png`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);log(`已保存第 ${i+1} 张图片`)}
async function fetchBlob(url){const absolute=new URL(url,location.href);const local=absolute.origin===location.origin?absolute.pathname+absolute.search:url;const r=local.startsWith('/uploads/')||local.startsWith('/outputs/')?await fetch(local,{cache:'no-store'}):await fetch('/api/fetch-image',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url})});if(!r.ok)throw Error(await r.text());return r.blob()}
async function downloadVisibleImages(items){for(const item of items){const blob=await fetchBlob(item.url),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`watch-detail-${item.index+1}.png`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);await new Promise(resolve=>setTimeout(resolve,120))}log(`已下载前端当前显示的 ${items.length} 张图片`)}
async function exportAll(){const cards=[...document.querySelectorAll('#resultGrid .result-card')],items=cards.map((card,index)=>({index,url:card.querySelector('.result-media img')?.currentSrc||card.querySelector('.result-media img')?.getAttribute('src')})).filter(item=>item.url);if(!items.length)throw Error('当前没有可导出的图片');const canPickFolder=window.isSecureContext&&typeof window.showDirectoryPicker==='function';if(canPickFolder){try{const dir=await window.showDirectoryPicker({id:'watch-studio-export',mode:'readwrite',startIn:'downloads'});for(const item of items){const handle=await dir.getFileHandle(`watch-detail-${item.index+1}.png`,{create:true});const writable=await handle.createWritable();await writable.write(await fetchBlob(item.url));await writable.close()}log(`已选择文件夹并导出前端当前显示的 ${items.length} 张图片`);return}catch(error){if(error?.name==='AbortError'){log('已取消选择导出文件夹');return}log('文件夹写入不可用，改用浏览器下载：'+error.message)}}await downloadVisibleImages(items)}
async function saveHistory(job=current){if(!job)return;await api('/api/history',{record:{id:job.generationId||job.id||crypto.randomUUID(),generationId:job.generationId||'',createdAt:job.createdAt||new Date().toISOString(),model:job.model,aspect:job.aspect,userPrompt:job.userPrompt||'',selling_points_cn:job.selling_points_cn,prompts:job.prompts,results:job.results,images:job.images}})}
async function loadHistory(){const j=await api('/api/history',null,'GET');history=j.records||[];$('historyList').innerHTML=history.length?history.map((x,idx)=>{const image=(x.results||[]).find(r=>r.url);return `<div class="history-item"><div>${image?`<img src="${esc(image.url)}">`:'<div style="width:72px;height:72px;background:#f3f5f8;border-radius:8px"></div>'}</div><div><strong>${new Date(x.createdAt||x.created_at).toLocaleString()}</strong><p>${esc(x.userPrompt||x.prompts?.[0]?.prompt||'无总体要求')}</p><span class="status">${esc(x.model||'')} · ${x.results?.filter(r=>r.url).length||0} 张完成</span></div><button class="secondary" data-history="${idx}">载入</button></div>`}).join(''):'<div class="empty">暂无保存记录</div>';$('historyList').querySelectorAll('[data-history]').forEach(b=>b.onclick=()=>{current=JSON.parse(JSON.stringify(history[+b.dataset.history]));$('model').value=current.model||'gpt-image-2';$('aspect').value=current.aspect||'1:1';$('userPrompt').value=current.userPrompt||'';renderAnalysis();renderResults();window.scrollTo({top:0,behavior:'smooth'})})}
$('run').onclick=()=>run().catch(e=>{log(e.message);$('resultStatus').textContent='执行失败'});$('export').onclick=()=>exportAll().catch(e=>log(e.message));$('refresh').onclick=()=>current&&renderResults();$('historyBtn').onclick=()=>$('history').scrollIntoView({behavior:'smooth'});$('keyBtn').onclick=()=>{$('keyPanel').classList.toggle('hidden');$('apiKey').focus()};$('saveKey').onclick=async()=>{await api('/api/keys',{hfsy:$('apiKey').value.trim()});log('API Key 已保存到服务器')};$('clearKey').onclick=async()=>{await api('/api/keys',{hfsy:''});$('apiKey').value='';log('API Key 已清除')};$('reloadHistory').onclick=loadHistory;loadHistory().catch(e=>log(e.message));api('/api/keys',null,'GET').then(x=>{$('apiKey').value=x.hfsy||''}).catch(()=>{});$('mode').onchange=refreshModeUI;refreshModeUI();$('clearThumbs').onclick=()=>{refs=[];$('files').value='';renderThumbs()};
function updateSuccessRate(){const vals=history.flatMap(x=>x.results||[]);const done=vals.filter(x=>x.status==='success'||x.status==='error');const rate=done.length?Math.round(done.filter(x=>x.status==='success').length/done.length*100):null;const el=$('successRate');if(el)el.textContent=rate===null?'生图成功率：暂无数据':`生图成功率：${rate}%（${done.filter(x=>x.status==='success').length}/${done.length}）`}
function addApiTools(){const select=$('analyzeModel');if(select&&!$('testAnalysisApi')){const b=document.createElement('button');b.id='testAnalysisApi';b.className='secondary';b.textContent='测试分析 API';b.style.cssText='margin-top:8px;width:100%;font-size:12px';b.onclick=async()=>{b.disabled=true;b.textContent='测试中…';try{const r=await api('/api/test-analysis',{});log(`分析 API 正常 · ${r.model} · ${r.latencyMs} ms`);b.textContent=`API 正常（${r.latencyMs} ms）`;b.style.color='var(--green)'}catch(e){log(`分析 API 测试失败：${e.message}`);b.textContent='API 测试失败';b.style.color='var(--red)'}finally{setTimeout(()=>{b.disabled=false},1500)}};select.parentElement.appendChild(b)}const rs=$('resultStatus');if(rs&&!$('successRate')){const el=document.createElement('span');el.id='successRate';el.className='status';el.style.cssText='display:block;margin-top:4px';rs.parentElement.appendChild(el)}updateSuccessRate()}
function enhanceUi(){const s=document.createElement('style');s.textContent='.sidebar{padding:24px}.ui-intro{background:linear-gradient(135deg,#f6f8ff,#fff);border:1px solid #e0e7ff;border-radius:14px;padding:13px 14px;margin:-2px 0 18px}.ui-intro strong{display:block;font-size:13px;margin-bottom:4px}.ui-intro span{font-size:11px;color:var(--muted);line-height:1.55}.choice-label{font-size:12px;font-weight:700;color:#526074;margin:16px 0 8px}.choice-grid{display:grid;gap:8px}.choice-grid.two{grid-template-columns:1fr 1fr}.choice-card{border:1px solid #dfe4ec;border-radius:11px;background:#fff;color:#344054;padding:11px 10px;text-align:left;cursor:pointer;transition:.15s}.choice-card strong{display:block;font-size:12px}.choice-card small{display:block;color:var(--muted);font-size:10px;line-height:1.4;margin-top:4px}.choice-card.active{border-color:var(--blue);background:#f2f5ff;box-shadow:0 0 0 3px #edf1ff;color:#173fc1}.choice-card.active small{color:#526da9}.paste-hint{display:block;margin-top:8px;color:#526da9!important;font-size:11px!important}.dropzone{padding:20px 14px}.dropzone strong{font-size:13px}.advanced-model{opacity:.8}.advanced-model select{background:#f8fafc}.legacy-choice{position:absolute;opacity:0;pointer-events:none;width:1px;height:1px}.simple-divider{height:1px;background:var(--line);margin:20px 0}.quick-actions{display:flex;gap:8px;margin-top:9px}.quick-actions button{flex:1;font-size:11px;padding:8px}.paste-flash{animation:pasteFlash .7s ease}@keyframes pasteFlash{50%{border-color:var(--blue);background:#eef3ff}}';document.head.appendChild(s);const mode=$('mode'),model=$('model');if(mode&&!$('uiIntro')){const intro=document.createElement('div');intro.id='uiIntro';intro.className='ui-intro';intro.innerHTML='<strong>三步完成一套详情图</strong><span>粘贴或拖入参考图 → 选择生成方式 → 点击开始。第一张图决定手表身份，其余图片只辅助细节和风格。</span>';const first=mode.closest('.field');first.parentElement.insertBefore(intro,first);const makeChoices=(sel,title,items,cls)=>{const field=sel.closest('.field');field.classList.add('choice-field');const label=field.querySelector('label');label.classList.add('choice-label');const grid=document.createElement('div');grid.className='choice-grid '+(cls||'');items.forEach(item=>{const b=document.createElement('button');b.type='button';b.className='choice-card';b.dataset.value=item.value;b.innerHTML=`<strong>${item.title}</strong><small>${item.note}</small>`;b.onclick=()=>{sel.value=item.value;sel.dispatchEvent(new Event('change'));sync()};grid.appendChild(b)});field.insertBefore(grid,sel);sel.classList.add('legacy-choice');function sync(){grid.querySelectorAll('.choice-card').forEach(b=>b.classList.toggle('active',b.dataset.value===sel.value))}sel.addEventListener('change',sync);sync()};makeChoices(mode,'生成方式',[{value:'analyze',title:'智能分析并生成',note:'自动提炼卖点，生成多张详情图'},{value:'prompt',title:'直接按提示词生成',note:'适合已有完整提示词的情况'}],'two');makeChoices(model,'生图模型',[{value:'gpt-image-2',title:'GPT Image 2',note:'细节与商品图表现优先'},{value:'nano-banana-2',title:'Nano Banana 2',note:'适合参考图套图与风格迁移'}],'two')}const dz=document.querySelector('.dropzone');if(dz&&!dz.querySelector('.paste-hint')){const h=document.createElement('small');h.className='paste-hint';h.textContent='也可以直接在本页面按 ⌘V / Ctrl+V 粘贴图片';dz.appendChild(h)}document.addEventListener('paste',async e=>{const files=[];for(const item of e.clipboardData?.items||[]){if(item.kind==='file'&&item.type.startsWith('image/')){const f=item.getAsFile();if(f)files.push(new File([f],`pasted-${Date.now()}-${files.length+1}.${f.type.split('/')[1]||'png'}`,{type:f.type}))}}if(!files.length)return;e.preventDefault();let added=0;for(const f of files){if(refs.length>=7)break;refs.push({file:f,preview:URL.createObjectURL(f)});added++}renderThumbs();if(dz)dz.classList.add('paste-flash');setTimeout(()=>dz&&dz.classList.remove('paste-flash'),800);log(`已从剪贴板添加 ${added} 张图片`)});const advanced=$('analyzeModel')?.closest('.field');if(advanced)advanced.classList.add('advanced-model')}
// Output count and generation mode are independent. Choosing direct-prompt mode
// defaults the count to one; selecting one image must not switch modes.
$('run').onclick=()=>run().catch(e=>{log(e.message);$('resultStatus').textContent='执行失败'});
$('export').onclick=()=>exportAll().catch(e=>log(e.message));
$('refresh').onclick=()=>current&&renderResults();
$('historyBtn').onclick=()=>$('history').scrollIntoView({behavior:'smooth'});
$('keyBtn').onclick=()=>{$('keyPanel').classList.toggle('hidden');$('apiKey').focus()};
$('saveKey').onclick=async()=>{await api('/api/keys',{hfsy:$('apiKey').value.trim()});log('API Key 已保存到服务器')};
$('clearKey').onclick=async()=>{await api('/api/keys',{hfsy:''});$('apiKey').value='';log('API Key 已清除')};
$('reloadHistory').onclick=loadHistory;loadHistory().catch(e=>log(e.message));
api('/api/keys',null,'GET').then(x=>{$('apiKey').value=x.hfsy||''}).catch(()=>{});
$('mode').onchange=refreshModeUI;
$('count').onchange=()=>refreshModeUI();
refreshModeUI();$('clearThumbs').onclick=()=>{refs=[];$('files').value='';renderThumbs()};
addApiTools();enhanceUi();setInterval(updateSuccessRate,3000);
</script><script>
(()=>{const clean=()=>{document.querySelector('.hero')?.remove();document.querySelector('.ui-intro')?.remove();document.querySelector('.brand p')?.remove();document.querySelectorAll('.sidebar .section-title p,.sidebar .note').forEach(x=>x.remove());const am=document.querySelector('#analyzeModel');if(am){am.value='gpt-5.6-terra';am.disabled=true;const f=am.closest('.field');if(f){const l=f.querySelector('label');if(l)l.innerHTML='分析 API <span>GPT-5.6 Terra · 已固定</span>';am.style.display='none'}}const test=document.querySelector('#testAnalysisApi');if(test){test.textContent='测试分析 API';test.style.marginTop='8px'}document.querySelectorAll('.content>.panel,.content>.logs').forEach(x=>x.style.boxShadow='0 4px 18px rgba(26,39,68,.035)');document.querySelector('.workspace')?.classList.add('simple-page')};clean()})()
</script><script>
(()=>{function boot(){var style=document.createElement('style');style.textContent=`
:root{background:#f6f8fc}.topbar{height:64px;padding:0 28px}.brand-mark{width:32px;height:32px}.brand p,.hero,.ui-intro,.sidebar>.section-title,.sidebar>.note{display:none!important}.shell{max-width:1080px;padding:28px 24px 56px}.workspace{display:block!important}.sidebar{position:static!important;padding:0!important;border:0!important;box-shadow:none!important;background:transparent!important}.builder{background:#fff;border:1px solid #e3e8f0;border-radius:18px;padding:24px;margin-bottom:18px;box-shadow:0 8px 30px rgba(24,39,75,.04)}.builder-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:22px}.builder-head h2{font-size:18px;margin:0;letter-spacing:-.02em}.builder-head span{font-size:11px;color:#61708a;background:#f2f5fa;border-radius:99px;padding:5px 9px}.build-section{padding:18px 0;border-top:1px solid #edf0f4}.build-section:first-of-type{padding-top:0;border-top:0}.build-title{font-weight:750;font-size:13px;color:#27364f;margin-bottom:10px}.build-title small{font-weight:500;color:#8190a6;margin-left:7px}.builder .field{margin:0}.builder .field>label{margin-bottom:9px}.builder .dropzone{padding:27px 18px;border-radius:13px;background:#fafcff;border-color:#b9c8e5}.builder .dropzone strong{font-size:14px;color:#244b9c}.builder .dropzone small{display:none}.ui-switch{display:grid;grid-template-columns:1fr 1fr;gap:10px}.ui-switch button{border:1px solid #dfe6ef;border-radius:12px;background:#fff;padding:13px;text-align:left;color:#334155;transition:.15s}.ui-switch button b{display:block;font-size:13px}.ui-switch button span{display:block;margin-top:4px;font-size:11px;color:#7a889c}.ui-switch button.active{border-color:#2b5cf6;background:#f1f4ff;color:#1f4bd8;box-shadow:0 0 0 3px #edf1ff}.ui-switch button.active span{color:#5874bf}.builder .split{gap:12px}.builder .split .field label{font-size:12px}.builder textarea{min-height:102px}.builder .primary{height:46px;margin-top:18px;border-radius:11px;font-size:14px}.builder #keyPanel{margin-top:16px}.analysis-card,.results,.logs,.history{border-radius:18px!important}.content{margin-top:0}.simple-status{font-size:11px;color:#697a94;margin-top:8px}.ref-paste{font-size:11px;color:#6a7c9b;text-align:center;margin-top:9px}.analysis-api-field{display:none!important}@media(max-width:650px){.topbar{padding:0 16px}.shell{padding:18px 14px 40px}.builder{padding:18px}.ui-switch{grid-template-columns:1fr}.builder .split{grid-template-columns:1fr 1fr}}
`;document.head.appendChild(style);
var aside=document.querySelector('.sidebar');if(!aside||document.getElementById('builder'))return;
document.querySelectorAll('.choice-grid,.ui-intro').forEach(function(x){x.remove()});
function field(id){var e=document.getElementById(id);return e?e.closest('.field'):null}var mode=field('mode'),model=field('model'),analysis=field('analyzeModel'),refs=field('files'),prompt=field('userPrompt'),ratio=document.getElementById('aspect')?document.getElementById('aspect').closest('.split'):null,run=document.getElementById('run'),keys=document.getElementById('keyPanel');
if(analysis){analysis.classList.add('analysis-api-field');var am=document.getElementById('analyzeModel');if(am){am.value='gpt-5.6-terra';am.disabled=true}}
var builder=document.createElement('section');builder.id='builder';builder.className='builder';builder.innerHTML='<div class="builder-head"><h2>创建商品详情图</h2><span>分析 API · GPT-5.6 Terra</span></div>';aside.insertBefore(builder,aside.firstChild);
function section(title,optional){var s=document.createElement('div');s.className='build-section';s.innerHTML='<div class="build-title">'+title+(optional?'<small>'+optional+'</small>':'')+'</div>';builder.appendChild(s);return s}
function switcher(s,select,choices){select.style.display='none';var box=document.createElement('div');box.className='ui-switch';choices.forEach(function(c){var b=document.createElement('button');b.type='button';b.innerHTML='<b>'+c[1]+'</b>';b.onclick=function(){select.value=c[0];select.dispatchEvent(new Event('change'));sync()};box.appendChild(b)});function sync(){Array.prototype.forEach.call(box.children,function(b,i){b.classList.toggle('active',choices[i][0]===select.value)})}select.addEventListener('change',sync);s.appendChild(box);sync()}
var up=section('参考图片','第一张为产品主体');up.appendChild(refs);var paste=document.createElement('div');paste.className='ref-paste';paste.textContent='点击、拖入，或直接按 ⌘V / Ctrl+V 粘贴图片';up.appendChild(paste);
var how=section('生成方式');how.appendChild(mode);switcher(how,document.getElementById('mode'),[['analyze','智能分析生成','自动分析卖点并输出详情图'],['prompt','直接提示词生图','已有完整提示词时使用']]);
var which=section('生图模型');var imageModel=document.getElementById('model');[['gemini-3.1-flash-image-preview','gemini-3.1-flash-image-preview'],['gpt-image-2.5','gpt-image-2.5']].forEach(function(entry){if(!Array.prototype.some.call(imageModel.options,function(o){return o.value===entry[0]})){var option=document.createElement('option');option.value=entry[0];option.textContent=entry[1];imageModel.appendChild(option)}});which.appendChild(model);switcher(which,imageModel,[['gpt-image-2','GPT Image 2','细节与商品图表现优先'],['gpt-image-2.5','GPT Image 2.5','与 GPT Image 2 相同的调用方式'],['nano-banana-2','Nano Banana 2','参考图套图与风格迁移'],['gemini-3.1-flash-image-preview','Gemini 3.1 Flash Image','新版图像模型，已完成调用测试']]);
var analyst=section('分析模型');var analysisModel=document.getElementById('analyzeModel');analysisModel.disabled=false;if(!Array.prototype.some.call(analysisModel.options,function(o){return o.value==='gpt-5.6-sol'})){var solOption=document.createElement('option');solOption.value='gpt-5.6-sol';solOption.textContent='gpt-5.6-sol';analysisModel.appendChild(solOption)}analysisModel.value='gpt-5.6-terra';analyst.appendChild(analysisModel);switcher(analyst,analysisModel,[['gpt-5.6-terra','GPT-5.6 Terra',''],['gpt-5.6-sol','GPT-5.6 Sol','']]);var req=section('创意要求','可选');req.appendChild(prompt);var set=section('画面设置');set.appendChild(ratio);builder.appendChild(run);if(keys)builder.appendChild(keys);
var test=document.getElementById('testAnalysisApi');if(test)test.remove();document.querySelectorAll('.sidebar>.field,.sidebar>.split').forEach(function(x){if(!builder.contains(x)&&x!==analysis)x.remove()});}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot()})()
</script><script>
(()=>{const style=document.createElement('style');style.textContent=`.work-state{min-height:184px;display:flex;flex-direction:column;justify-content:center;align-items:center;gap:11px;text-align:center;color:#53647d}.work-state strong{font-size:15px;color:#24334b}.work-state span{font-size:12px;color:#7a899e}.spinner{width:24px;height:24px;border:3px solid #dce6ff;border-top-color:#2b5cf6;border-radius:50%;animation:watchspin .8s linear infinite}.result-media .spinner{width:22px;height:22px;border-width:3px;margin:auto}@keyframes watchspin{to{transform:rotate(360deg)}}.result-media.loading{display:flex;align-items:center;justify-content:center;flex-direction:column;gap:9px;color:#65748b;font-size:12px}`;document.head.appendChild(style);window.watchLoading=false;function waiting(title,detail){return '<div class="work-state"><i class="spinner"></i><strong>'+title+'</strong><span>'+detail+'</span></div>'}window.renderResults=function(){const grid=$('resultGrid'),items=current?.results||[];if(!items.length){grid.innerHTML=window.watchLoading?waiting('思考中…','正在上传参考图并分析商品卖点'):'<div class="empty">上传参考图并点击“分析并生成”</div>';return}grid.innerHTML=items.map((x,i)=>{const title=esc(current.prompts[i]?.title||'详情图');const media=x.url?'<img src="'+esc(x.url)+'">':x.status==='error'?'生成失败<br>'+esc(x.error||'请重新生成'):'<i class="spinner"></i><span>生成中…</span>';return '<article class="result-card"><div class="result-media '+(x.status==='error'?'error':x.url?'':'loading')+'">'+media+'</div><div class="result-meta"><strong>'+String(i+1)+'. '+title+'</strong><small>'+(x.status==='success'?'已完成':x.status==='error'?'失败':'生成中…')+'</small><div class="result-actions"><button class="secondary regen" data-i="'+i+'">重新生成</button>'+(x.url?'<button class="secondary save" data-i="'+i+'">保存图片</button>':'')+'</div></div></article>'}).join('');grid.querySelectorAll('.regen').forEach(b=>b.onclick=()=>regen(+b.dataset.i));grid.querySelectorAll('.save').forEach(b=>b.onclick=()=>saveOne(+b.dataset.i))};const previousRun=window.run;window.run=async function(){window.watchLoading=true;renderResults();try{await previousRun()}finally{window.watchLoading=false;if($('resultStatus').textContent==='执行失败')$('resultGrid').innerHTML='<div class="work-state"><strong>分析未完成</strong><span>请展开运行日志查看错误后重试</span></div>'}}})();
</script><script>
(()=>{const status=$('resultStatus');function refreshProgress(){if(!window.watchLoading)return;const text=status.textContent||'';const box=$('resultGrid').querySelector('.work-state');if(!box)return;let title='思考中…',detail='正在分析商品卖点并规划详情图';if(text.includes('上传')){title='准备中…';detail='正在上传参考图片'}else if(text.includes('GPT-5.4')||text.includes('分析中')){title='思考中…';detail='GPT-5.6 Terra 正在分析商品卖点'}box.querySelector('strong').textContent=title;box.querySelector('span').textContent=detail}new MutationObserver(refreshProgress).observe(status,{childList:true,characterData:true,subtree:true});const wrappedRun=window.run;window.run=async function(){const result=await wrappedRun();refreshProgress();return result}})();
</script><script>
(()=>{const originalApi=window.api;window.api=function(path,body,method){if(path==='/api/analyze'&&body)body.analysisUpstream=document.getElementById('analysisUpstream')?.value||'owlai';return originalApi(path,body,method)};const panel=document.getElementById('keyPanel');if(!panel||document.getElementById('analysisKeys'))return;const keys=document.createElement('div');keys.id='analysisKeys';keys.innerHTML='<div class="field" style="margin-top:14px"><label>OwlAI 分析 Key</label><input id="owlaiAnalysisKey" type="password" placeholder="sk-..."><button type="button" class="secondary" id="saveOwlaiAnalysisKey" style="margin-top:8px;width:100%">保存 OwlAI Key</button></div><div class="field" style="margin-top:14px"><label>TyAI 分析 Key</label><input id="tyaiAnalysisKey" type="password" placeholder="sk-..."><button type="button" class="secondary" id="saveTyaiAnalysisKey" style="margin-top:8px;width:100%">保存 TyAI Key</button></div>';panel.appendChild(keys);[['owlai','owlaiAnalysisKey','saveOwlaiAnalysisKey'],['tyai','tyaiAnalysisKey','saveTyaiAnalysisKey']].forEach(function(item){document.getElementById(item[2]).onclick=async function(){const value=document.getElementById(item[1]).value.trim();if(!value){log('请输入分析 Key');return}this.disabled=true;try{await originalApi('/api/analysis-key',{upstream:item[0],analysis:value});document.getElementById(item[1]).value='';log(item[0]+' 分析 Key 已保存到服务器')}catch(error){log(error.message)}finally{this.disabled=false}}})})();
</script><script>
(()=>{const top=document.querySelector('.top-actions'),historyButton=document.getElementById('historyBtn');if(top&&historyButton&&!document.getElementById('analysisUpstream')){const control=document.createElement('label');control.className='secondary';control.style.cssText='display:flex;align-items:center;gap:7px;padding:0 10px;height:36px;font-size:12px';control.innerHTML='分析上游 <select id="analysisUpstream" style="border:0;background:transparent;color:#263852;font-weight:700;outline:0"><option value="owlai">OwlAI</option><option value="tyai">TyAI</option></select>';top.insertBefore(control,historyButton);const select=control.querySelector('select');select.value=localStorage.getItem('watch-analysis-upstream')||'owlai';select.onchange=()=>localStorage.setItem('watch-analysis-upstream',select.value)}const taskApi=window.api;window.loadHistory=async function(){const data=await taskApi('/api/history',null,'GET'),records=data.records||[],list=document.getElementById('historyList');const state={analyzing:'分析中',queued:'排队中',generating:'生成中',completed:'已完成',partial:'部分完成',failed:'失败'};list.innerHTML=records.length?records.map((item,index)=>{const result=(item.results||[]).find(x=>x.url),total=(item.results||[]).length,done=(item.results||[]).filter(x=>x.url).length,label=state[item.status]||((done===total&&total)?'已完成':'生成中');return '<div class="history-item"><div>'+(result?'<img src="'+esc(result.url)+'">':'<div style="width:72px;height:72px;background:#f3f5f8;border-radius:8px;display:grid;place-items:center;color:#7b8aa0;font-size:11px">'+label+'</div>')+'</div><div><strong>'+new Date(item.createdAt||item.created_at).toLocaleString()+'</strong><p>'+esc(item.userPrompt||item.prompts?.[0]?.prompt||'无总体要求')+'</p><span class="status">'+label+' · '+done+'/'+total+' 张</span></div><button class="secondary" data-task="'+index+'">载入</button></div>'}).join(''):'<div class="empty">暂无保存记录</div>';list.querySelectorAll('[data-task]').forEach(button=>button.onclick=()=>{const item=records[+button.dataset.task];current=JSON.parse(JSON.stringify(item));current._watchLoaded=true;document.getElementById('model').value=current.model||'gpt-image-2';document.getElementById('aspect').value=current.aspect||'1:1';document.getElementById('userPrompt').value=current.userPrompt||'';renderAnalysis();renderResults();window.scrollTo({top:0,behavior:'smooth'})})};document.getElementById('reloadHistory').onclick=()=>window.loadHistory().catch(error=>log(error.message));setInterval(()=>window.loadHistory().catch(()=>{}),5000);window.run=async function(){if(!refs.length)throw Error('请先上传至少 1 张参考图');const button=document.getElementById('run');button.disabled=true;window.watchLoading=true;renderResults();try{const images=await uploadAll(),mode=document.getElementById('mode').value;const task=await taskApi('/api/tasks',{images,userPrompt:document.getElementById('userPrompt').value.trim(),count:+document.getElementById('count').value,model:document.getElementById('model').value,aspect:document.getElementById('aspect').value,analyzeModel:document.getElementById('analyzeModel').value,analysisUpstream:document.getElementById('analysisUpstream')?.value||'owlai',mode});refs=[];document.getElementById('files').value='';renderThumbs();document.getElementById('userPrompt').value='';current=null;window.watchLoading=false;document.getElementById('resultGrid').innerHTML='<div class="work-state"><strong>任务已在后台运行</strong><span>可继续创建下一任务</span></div>';log('后台任务已创建：'+task.generationId);await window.loadHistory()}catch(error){window.watchLoading=false;renderResults();throw error}finally{button.disabled=false}};document.getElementById('run').onclick=()=>window.run().catch(error=>{log(error.message);document.getElementById('resultStatus').textContent='执行失败'})})();
</script><script>
(()=>{const historyLoader=window.loadHistory;window.loadHistory=async function(){await historyLoader();document.querySelectorAll('[data-task]').forEach(button=>{const previous=button.onclick;button.onclick=()=>{previous();refs=(current.images||[]).map((url,index)=>({url,preview:url,remote:true,name:'参考图 '+(index+1)}));renderThumbs();const hasPrompts=Array.isArray(current.prompts)&&current.prompts.length>0;if(!hasPrompts){document.getElementById('analysis').classList.add('hidden');document.getElementById('resultGrid').innerHTML='<div class="work-state"><i class="spinner"></i><strong>分析中…</strong><span>正在生成提示词</span></div>'}}})}})();
</script><script>
(()=>{const historyLoader=window.loadHistory;window.loadHistory=async function(){await historyLoader();document.querySelectorAll('[data-task]').forEach(button=>{const previous=button.onclick;button.onclick=()=>{previous();const active=(current.results||[]).some(item=>item.url||item.taskId||['creating','polling','success','error'].includes(item.status));if(active){renderResults();return}document.getElementById('resultGrid').innerHTML='<div class="work-state"><i class="spinner"></i><strong>分析中…</strong></div>'}})}})();
</script><script>
(()=>{const drawResults=window.renderResults;window.renderResults=function(){const prompts=current?.prompts||[];if(current&&current.status==='failed'){document.getElementById('resultGrid').innerHTML='<div class="work-state"><strong>分析失败，未发出生图请求</strong></div>';return}if(current&&(!prompts.length||current.status==='analyzing')){document.getElementById('resultGrid').innerHTML='<div class="work-state"><i class="spinner"></i><strong>分析中…</strong></div>';return}return drawResults()}})();
</script><script>
(()=>{const select=document.getElementById('analysisUpstream');if(select){select.value='tyai';localStorage.setItem('watch-analysis-upstream','tyai')}})();
</script><script>
(()=>{const priorLoadHistory=window.loadHistory;let syncing=false;window.loadHistory=async function(){await priorLoadHistory();if(syncing||!current?._watchLoaded)return;syncing=true;try{const response=await fetch('/api/history',{cache:'no-store'});if(!response.ok)return;const data=await response.json(),fresh=(data.records||[]).find(item=>item.generationId===current.generationId);if(!fresh)return;current=JSON.parse(JSON.stringify(fresh));current._watchLoaded=true;refs=(current.images||[]).map((url,index)=>({url,preview:url,remote:true,name:'参考图 '+(index+1)}));renderThumbs();if(Array.isArray(current.prompts)&&current.prompts.length){document.getElementById('analysis').classList.remove('hidden');renderAnalysis();renderResults()}else{document.getElementById('analysis').classList.add('hidden');document.getElementById('resultGrid').innerHTML='<div class="work-state"><i class="spinner"></i><strong>分析中…</strong></div>'}}catch(error){console.warn('任务状态同步失败',error)}finally{syncing=false}}})();
</script><script>
(()=>{const synchronizedLoadHistory=window.loadHistory;window.loadHistory=async function(){if(current?._watchLoaded){try{const response=await fetch('/api/history',{cache:'no-store'}),data=response.ok?await response.json():{},fresh=(data.records||[]).find(item=>item.generationId===current.generationId);const active=fresh&&(['analyzing','queued','generating'].includes(fresh.status)||(fresh.results||[]).some(item=>['queued','creating','retrying','polling'].includes(item.status)));if(!active)current._watchLoaded=false}catch(_){}}return synchronizedLoadHistory()};document.addEventListener('click',event=>{if(event.target.closest('#clearThumbs'))beginReuseEdit();if(event.target.closest('#historyList [data-task]'))setTimeout(()=>{if(current)current._historySourceId=current.generationId},0)},true);['userPrompt','model','aspect','count','mode'].forEach(id=>{const el=document.getElementById(id);if(el)el.addEventListener(id==='userPrompt'?'input':'change',beginReuseEdit)});document.getElementById('prompts')?.addEventListener('input',beginReuseEdit)})();
</script><script>
(()=>{const finishAwareLoadHistory=window.loadHistory;window.loadHistory=async function(){let finalSnapshot=null;if(current?._watchLoaded){try{const response=await fetch('/api/history',{cache:'no-store'}),data=response.ok?await response.json():{},fresh=(data.records||[]).find(item=>item.generationId===current.generationId);const active=fresh&&(['analyzing','queued','generating'].includes(fresh.status)||(fresh.results||[]).some(item=>['queued','creating','retrying','polling'].includes(item.status)));if(fresh&&!active)finalSnapshot=fresh}catch(_){}}if(finalSnapshot){current=JSON.parse(JSON.stringify(finalSnapshot));current._watchLoaded=false;current._historySourceId=current.generationId;refs=(current.images||[]).map((url,index)=>({url,preview:url,remote:true,name:'参考图 '+(index+1)}));renderThumbs();if(Array.isArray(current.prompts)&&current.prompts.length){document.getElementById('analysis').classList.remove('hidden');renderAnalysis()}renderResults()}return finishAwareLoadHistory()}})();
</script><script>
(()=>{const stageAwareRender=window.renderResults;window.renderResults=function(){if(current?.status==='failed'&&(current?.failureStage==='image_submit'||(current?.prompts||[]).length)){const saved=current.status;current.status='partial';try{return stageAwareRender()}finally{current.status=saved}}return stageAwareRender()};const stageAwareHistory=window.loadHistory;window.loadHistory=async function(){await stageAwareHistory();try{const response=await fetch('/api/history',{cache:'no-store'}),data=response.ok?await response.json():{};(data.records||[]).forEach((record,index)=>{if(record.status!=='failed'||!(record.failureStage==='image_submit'||(record.prompts||[]).length))return;const item=document.querySelectorAll('#historyList .history-item')[index],total=(record.results||[]).length,done=(record.results||[]).filter(result=>result.url).length;if(!item)return;const status=item.querySelector('.status');if(status)status.textContent='生图提交失败 · '+done+'/'+total+' 张';const marker=item.firstElementChild;if(marker&&!marker.querySelector('img'))marker.textContent='生图失败'})}catch(_){}}})();
</script><script>
(()=>{const input=document.getElementById('userPrompt');if(!input||document.getElementById('favoritePromptBar'))return;const field=input.closest('.field'),label=field.querySelector('label');label.innerHTML='总体要求 <span>可选</span>';const bar=document.createElement('div');bar.id='favoritePromptBar';bar.className='favorite-prompt-bar';bar.innerHTML='<button type="button" class="secondary" id="savePromptFavorite">☆ 收藏当前提示词</button><button type="button" class="ghost" id="openPromptFavorites">提示词收藏</button>';label.insertAdjacentElement('afterend',bar);const dialog=document.createElement('div');dialog.id='promptFavoritesModal';dialog.className='favorites-modal hidden';dialog.innerHTML='<div class="favorites-dialog"><header><div><strong>提示词收藏</strong><span>点击“使用”即可填入总体要求</span></div><button type="button" class="ghost" data-close>关闭</button></header><div id="promptFavoritesList" class="favorites-list"></div></div>';document.body.appendChild(dialog);const close=()=>dialog.classList.add('hidden');const render=async()=>{const data=await api('/api/prompt-favorites',null,'GET'),list=data.favorites||[],box=document.getElementById('promptFavoritesList');box.innerHTML=list.length?list.map(item=>'<article class="favorite-item"><div><strong>'+esc(item.title||'未命名提示词')+'</strong><p>'+esc(item.prompt||'')+'</p><small>收藏于 '+esc(new Date(item.createdAt||Date.now()).toLocaleString())+'</small></div><div class="favorite-actions"><button class="secondary" data-use="'+esc(item.id)+'">使用</button><button class="ghost danger" data-delete="'+esc(item.id)+'">删除</button></div></article>').join(''):'<div class="favorites-empty">还没有收藏提示词。填写总体要求后，点击“收藏当前提示词”。</div>';box.querySelectorAll('[data-use]').forEach(button=>button.onclick=()=>{const item=list.find(x=>x.id===button.dataset.use);if(!item)return;input.value=item.prompt||'';input.dispatchEvent(new Event('input',{bubbles:true}));close();input.focus();log('已载入收藏提示词：'+(item.title||''))});box.querySelectorAll('[data-delete]').forEach(button=>button.onclick=async()=>{if(!confirm('删除这条收藏提示词？'))return;await api('/api/prompt-favorites',{action:'delete',id:button.dataset.delete});await render()})};document.getElementById('savePromptFavorite').onclick=async()=>{const prompt=input.value.trim();if(!prompt){input.focus();log('请先输入要收藏的提示词');return}try{await api('/api/prompt-favorites',{action:'save',prompt});log('提示词已收藏')}catch(error){log(error.message)}};document.getElementById('openPromptFavorites').onclick=async()=>{dialog.classList.remove('hidden');document.getElementById('promptFavoritesList').innerHTML='<div class="favorites-empty">正在载入收藏…</div>';try{await render()}catch(error){document.getElementById('promptFavoritesList').innerHTML='<div class="favorites-empty">载入失败：'+esc(error.message)+'</div>'}};dialog.addEventListener('click',event=>{if(event.target===dialog||event.target.closest('[data-close]'))close()});const style=document.createElement('style');style.textContent='.favorite-prompt-bar{display:flex;gap:8px;margin:-1px 0 8px}.favorite-prompt-bar button{font-size:11px;padding:6px 9px}.favorites-modal{position:fixed;inset:0;z-index:50;background:rgba(15,23,42,.38);display:grid;place-items:center;padding:20px}.favorites-dialog{width:min(780px,100%);max-height:min(680px,88vh);overflow:auto;background:#fff;border-radius:16px;box-shadow:0 28px 70px rgba(15,23,42,.24);padding:20px}.favorites-dialog header{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:1px solid var(--line);padding-bottom:14px}.favorites-dialog header strong{display:block;font-size:16px}.favorites-dialog header span{display:block;font-size:12px;color:var(--muted);margin-top:4px}.favorites-list{display:grid;gap:10px;padding-top:14px}.favorite-item{display:flex;gap:14px;justify-content:space-between;border:1px solid var(--line);border-radius:12px;padding:13px}.favorite-item strong{font-size:13px}.favorite-item p{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;line-height:1.55;color:#526074;margin:7px 0}.favorite-item small{color:var(--muted);font-size:11px}.favorite-actions{display:flex;align-items:flex-start;gap:6px;flex:none}.favorite-actions button{font-size:11px;padding:7px 9px}.danger{color:var(--red)}.favorites-empty{text-align:center;color:var(--muted);font-size:12px;padding:46px 20px}@media(max-width:650px){.favorite-item{display:block}.favorite-actions{margin-top:10px}.favorites-dialog{padding:16px}}';document.head.appendChild(style)})();
</script><script>
(()=>{const modal=document.getElementById('promptFavoritesModal'),dialog=modal?.querySelector('.favorites-dialog');if(!modal||!dialog||document.getElementById('customPromptFavorite'))return;const header=dialog.querySelector('header'),custom=document.createElement('button');custom.type='button';custom.id='customPromptFavorite';custom.className='secondary';custom.textContent='新建提示词';header.insertBefore(custom,header.querySelector('[data-close]'));const editor=document.createElement('section');editor.id='favoritePromptEditor';editor.className='favorite-editor hidden';editor.innerHTML='<div class="favorite-editor-head"><strong id="favoriteEditorTitle">新建提示词</strong><button type="button" class="ghost" data-editor-close>取消</button></div><label>名称<input id="favoritePromptName" maxlength="80" placeholder="例如：轻奢商务腕表详情图"></label><label>提示词<textarea id="favoritePromptText" maxlength="20000" placeholder="输入可重复使用的提示词"></textarea></label><div class="favorite-editor-actions"><button type="button" class="secondary" data-editor-close>取消</button><button type="button" class="primary" id="saveCustomPromptFavorite">保存提示词</button></div></section>';dialog.appendChild(editor);let editingId='';const openEditor=item=>{editingId=item?.id||'';document.getElementById('favoriteEditorTitle').textContent=item?'编辑收藏提示词':'新建提示词';document.getElementById('favoritePromptName').value=item?.title||'';document.getElementById('favoritePromptText').value=item?.prompt||'';editor.classList.remove('hidden');document.getElementById('favoritePromptName').focus()};const closeEditor=()=>editor.classList.add('hidden');const addEditButtons=()=>document.querySelectorAll('#promptFavoritesList .favorite-actions').forEach(actions=>{if(actions.querySelector('[data-favorite-edit]'))return;const use=actions.querySelector('[data-use]'),button=document.createElement('button');button.type='button';button.className='ghost';button.textContent='编辑';button.dataset.favoriteEdit=use?.dataset.use||'';actions.insertBefore(button,actions.firstChild)});const observer=new MutationObserver(addEditButtons);observer.observe(document.getElementById('promptFavoritesList'),{childList:true,subtree:true});custom.onclick=()=>openEditor();document.addEventListener('click',async event=>{const edit=event.target.closest('[data-favorite-edit]');if(edit){const data=await api('/api/prompt-favorites',null,'GET'),item=(data.favorites||[]).find(x=>x.id===edit.dataset.favoriteEdit);if(item)openEditor(item)}if(event.target.closest('[data-editor-close]'))closeEditor()});document.getElementById('saveCustomPromptFavorite').onclick=async()=>{const title=document.getElementById('favoritePromptName').value.trim(),prompt=document.getElementById('favoritePromptText').value.trim();if(!prompt){document.getElementById('favoritePromptText').focus();return}const button=document.getElementById('saveCustomPromptFavorite');button.disabled=true;try{await api('/api/prompt-favorites',{action:'upsert',id:editingId,title,prompt});closeEditor();document.getElementById('openPromptFavorites').click();log(editingId?'收藏提示词已更新':'自定义提示词已收藏')}catch(error){log(error.message)}finally{button.disabled=false}};const style=document.createElement('style');style.textContent='.favorites-dialog header>.secondary{margin-left:auto;margin-right:8px}.favorite-editor{margin:14px 0 2px;border:1px solid #dfe6f5;background:#f8faff;border-radius:12px;padding:14px}.favorite-editor-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:11px}.favorite-editor label{display:block;font-size:12px;font-weight:700;color:#526074;margin-top:10px}.favorite-editor input,.favorite-editor textarea{margin-top:6px}.favorite-editor textarea{min-height:140px}.favorite-editor-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:12px}.favorite-editor-actions button{font-size:12px;padding:8px 12px}';document.head.appendChild(style);addEditButtons()})();
</script><script>(()=>{const arrangeBuilder=()=>{const builder=document.getElementById('builder');if(!builder)return;const sections=[...builder.querySelectorAll(':scope>.build-section')],find=name=>sections.find(section=>section.querySelector('.build-title')?.textContent.trim().startsWith(name)),references=find('参考图片'),creative=find('创意要求'),settings=find('画面设置');if(references&&creative&&references.nextElementSibling!==creative)references.insertAdjacentElement('afterend',creative);if(creative&&settings&&creative.nextElementSibling!==settings)creative.insertAdjacentElement('afterend',settings);const bar=document.getElementById('favoritePromptBar'),promptField=document.getElementById('userPrompt')?.closest('.field'),promptLabel=promptField?.querySelector('label');if(bar&&promptLabel&&bar.previousElementSibling!==promptLabel)promptLabel.insertAdjacentElement('afterend',bar)};arrangeBuilder();new MutationObserver(arrangeBuilder).observe(document.body,{childList:true,subtree:true})})();</script><style>#resultStatus,.work-state span{display:none!important}</style></body></html>'''

HTML_LAYOUT_FIX='<script>(()=>{const apply=()=>{const builder=document.getElementById("builder");if(!builder)return;builder.querySelector(".builder-head span")?.remove();const sections=[...builder.querySelectorAll(":scope>.build-section")],find=name=>sections.find(section=>section.querySelector(".build-title")?.textContent.trim().startsWith(name)),references=find("参考图片"),creative=find("创意要求");references?.querySelector(".build-title")?.remove();const promptField=creative?.querySelector("#userPrompt")?.closest(".field");promptField?.querySelector(":scope>label")?.remove();const paste=references?.querySelector(".ref-paste"),dropzone=references?.querySelector(".dropzone");if(paste&&dropzone)dropzone.appendChild(paste);const favoriteButton=document.getElementById("openPromptFavorites");if(favoriteButton){favoriteButton.classList.remove("ghost");favoriteButton.classList.add("secondary");favoriteButton.style.border="1px solid #d9a925";favoriteButton.style.background="#fffdf5";favoriteButton.style.color="#8b6500"}};apply();new MutationObserver(apply).observe(document.body,{childList:true,subtree:true})})();</script>'
HTML=HTML.replace('</script><style>#resultStatus,.work-state span{display:none!important}</style>','</script>'+HTML_LAYOUT_FIX+'<style>#resultStatus,.work-state span{display:none!important}</style>')
HTML_ORDER_FIX='<script>(()=>{const apply=()=>{const builder=document.getElementById("builder");if(!builder)return;const sections=[...builder.querySelectorAll(":scope>.build-section")],find=name=>sections.find(section=>section.querySelector(".build-title")?.textContent.trim().startsWith(name)),references=find("参考图片"),creative=find("创意要求"),settings=find("画面设置");if(references&&creative&&references.nextElementSibling!==creative)references.insertAdjacentElement("afterend",creative);if(creative&&settings&&creative.nextElementSibling!==settings)creative.insertAdjacentElement("afterend",settings)};if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",apply);else apply();new MutationObserver(apply).observe(document.body,{childList:true,subtree:true})})();</script>'
HTML=HTML.replace('</body></html>',HTML_ORDER_FIX+'</body></html>')
HTML_STABLE_ORDER_FIX='<script>(()=>{const apply=()=>{const reference=document.getElementById("files")?.closest(".build-section"),creative=document.getElementById("userPrompt")?.closest(".build-section"),settings=document.getElementById("aspect")?.closest(".split")?.closest(".build-section");if(reference&&creative&&reference.nextElementSibling!==creative)reference.insertAdjacentElement("afterend",creative);if(creative&&settings&&creative.nextElementSibling!==settings)creative.insertAdjacentElement("afterend",settings)};if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",apply);else apply();new MutationObserver(apply).observe(document.body,{childList:true,subtree:true})})();</script>'
HTML=HTML.replace('</body></html>',HTML_STABLE_ORDER_FIX+'</body></html>')
HTML_FIXED_RACE_UI='<script>(()=>{const select=document.getElementById("analysisUpstream"),wrap=select?.closest("label");if(wrap)wrap.remove();else[...document.querySelectorAll("label")].find(item=>item.textContent.includes("分析上游"))?.remove()})();</script>'
HTML=HTML.replace('</body></html>',HTML_FIXED_RACE_UI+'</body></html>')
HTML_HIDE_RACE_UI='<script>(()=>{const select=document.getElementById("analysisUpstream");select?.closest("label")?.remove();[...document.querySelectorAll("label")].find(item=>item.textContent.includes("分析上游"))?.remove()})();</script>'
HTML=HTML.replace('</body></html>',HTML_HIDE_RACE_UI+'</body></html>')
HTML_HISTORY_RIGHT_FIX='''<script>(()=>{
const moveHistory=()=>{
  const workspace=document.querySelector('.workspace'),history=document.getElementById('history'),content=document.querySelector('.content');
  if(workspace&&history&&content&&history.parentElement!==workspace)workspace.appendChild(history);
};
const style=document.createElement('style');
style.textContent=`
  .shell{max-width:1680px!important;padding:18px 20px 40px!important}
  .workspace{display:grid!important;grid-template-columns:300px minmax(0,1fr) 330px!important;gap:16px!important;align-items:start!important}
  .sidebar{position:sticky!important;top:88px!important;margin-bottom:0!important;max-height:calc(100vh - 106px);overflow:auto}
  .content{min-width:0!important}
  #history.history{grid-column:auto!important;margin:0!important;position:sticky!important;top:88px!important;max-height:calc(100vh - 106px);overflow:auto;padding:16px!important}
  #history .toolbar{position:sticky;top:-16px;z-index:2;background:#fff;margin:0 -2px 12px;padding:2px 2px 12px;border-bottom:1px solid var(--line)}
  #history .toolbar h2{font-size:15px}
  #history .history-list{display:grid;gap:9px}
  #history .history-item{grid-template-columns:56px minmax(0,1fr);gap:8px;padding:10px}
  #history .history-item img,#history .history-item>div:first-child>div{width:56px!important;height:56px!important}
  #history .history-item p{font-size:11px;line-height:1.45;margin:4px 0;white-space:normal;overflow-wrap:anywhere;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;overflow:hidden}
  #history .history-item .secondary{grid-column:2;justify-self:end;padding:6px 10px;font-size:11px}
  .top-actions #historyBtn{display:none!important}
  .logs{display:none!important}
  @media(max-width:1280px){
    .workspace{grid-template-columns:280px minmax(0,1fr)!important}
    #history.history{grid-column:1/-1;position:static!important;max-height:none;display:block}
    #history .history-list{grid-template-columns:repeat(2,minmax(0,1fr))}
  }
  @media(max-width:760px){
    .shell{padding:14px 12px 30px!important}
    .workspace{grid-template-columns:1fr!important}
    #history.history{grid-column:auto}
    #history .history-list{grid-template-columns:1fr}
    .sidebar{position:static!important;max-height:none;overflow:visible}
  }
`;
const finalize=()=>{document.head.appendChild(style);moveHistory()};
finalize();
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',finalize);
setTimeout(finalize,0);
})();</script>'''
HTML=HTML.replace('</body></html>',HTML_HISTORY_RIGHT_FIX+'</body></html>')
HTML_HISTORY_BELOW_RESULTS_FIX='''<script>(()=>{
const place=()=>{
  const content=document.querySelector('.content'),results=document.querySelector('.results'),history=document.getElementById('history');
  if(content&&results&&history)results.insertAdjacentElement('afterend',history);
};
const style=document.createElement('style');
style.textContent=`
  .workspace{grid-template-columns:minmax(360px,40%) minmax(0,1fr)!important}
  #history.history{grid-column:auto!important;position:static!important;max-height:none!important;overflow:visible!important;margin:0!important;padding:20px!important}
  #history .toolbar{position:static;background:transparent;margin:0 0 12px;padding:0 0 12px;border-bottom:1px solid var(--line)}
  #history .history-list{grid-template-columns:repeat(2,minmax(0,1fr))}
  #history .history-item{grid-template-columns:72px minmax(0,1fr) auto}
  #history .history-item .secondary{grid-column:auto;justify-self:auto}
  .logs{display:none!important}
  @media(max-width:760px){
    .workspace{grid-template-columns:1fr!important}
    #history .history-list{grid-template-columns:1fr}
    #history .history-item{grid-template-columns:56px minmax(0,1fr)}
    #history .history-item .secondary{grid-column:2;justify-self:end}
  }
`;
const finalize=()=>{document.head.appendChild(style);place()};
finalize();
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',finalize);
setTimeout(finalize,0);
})();</script>'''
HTML=HTML.replace('</body></html>',HTML_HISTORY_BELOW_RESULTS_FIX+'</body></html>')
HTML_REGEN_DIRECTION_FIX='''<script>(()=>{
const install=()=>{
  if(document.getElementById('regenDirectionModal'))return;
  const modal=document.createElement('div');modal.id='regenDirectionModal';modal.className='regen-direction-modal hidden';
  modal.innerHTML='<div class="regen-direction-dialog"><div class="regen-direction-head"><div><strong>定向重新生成</strong><span id="regenDirectionTitle">调整第 1 张图片</span></div><button type="button" class="ghost" data-close>关闭</button></div><p class="regen-direction-note">默认只做局部修改：保留原背景、场景、机位、光线、文字和整体构图；留空则按原提示词重生成。</p><div class="regen-direction-chips"><button type="button" data-direction="保留原背景和场景，只在原画面内微调主体位置和大小，避免改变整体构图。">局部调整</button><button type="button" data-direction="在原背景和场景中适度放大产品，保持原机位、透视和构图不变。">放大主体</button><button type="button" data-direction="只移除指定的道具或装饰，并用原背景的纹理、光线和阴影自然补齐。">减少道具</button><button type="button" data-direction="保留原背景、场景和光线，只调整局部环境细节，不要换场景。">改局部场景</button><button type="button" data-direction="保留原构图和场景，只增强真实摄影感，修正不自然的物体、结构和比例。">增强实拍</button></div><textarea id="regenDirectionText" placeholder="可留空按原提示词重生成；例如：去掉礼盒中的空白卡片，保留礼盒、桌面、背景和原有光线，只放大手表并完整展示表盘和表链。"></textarea><div class="regen-direction-actions"><button type="button" class="ghost" data-close>取消</button><button type="button" class="primary" id="confirmRegenDirection">按此方向重新生成</button></div></div>';
  document.body.appendChild(modal);
  const input=modal.querySelector('#regenDirectionText'),title=modal.querySelector('#regenDirectionTitle'),confirm=modal.querySelector('#confirmRegenDirection');let targetIndex=-1;
  const close=()=>{modal.classList.add('hidden');targetIndex=-1};
  const open=index=>{targetIndex=index;title.textContent='调整第 '+(index+1)+' 张图片';input.value='';modal.classList.remove('hidden');setTimeout(()=>input.focus(),0)};
  modal.addEventListener('click',event=>{if(event.target===modal||event.target.closest('[data-close]'))close();const chip=event.target.closest('[data-direction]');if(chip){input.value=input.value?input.value+'\\n'+chip.dataset.direction:chip.dataset.direction;input.focus()}});
  document.addEventListener('click',event=>{const button=event.target.closest('.regen');if(!button)return;event.preventDefault();event.stopPropagation();open(+button.dataset.i)},true);
  const baseRegen=window.regen;
  const runWithDirection=async(index,direction)=>{
    const job=current;if(!job?.generationId)throw Error('未找到当前任务，无法重新生成');
    const textarea=document.querySelector('textarea[data-prompt="'+index+'"]');const base=textarea?textarea.value:promptText(job.prompts[index]);
    const composed='LOCAL EDIT ONLY (highest priority for this image).\\nUse the attached reference image as the source and apply only this user-requested local change: '+direction+'\\nPreserve exactly unless the direction explicitly names it: the original background, scene or set, camera angle, framing, perspective, overall composition and layout, lighting, shadows, color palette, typography and visible copy, product identity, materials, proportions, and aspect ratio. Change the smallest possible area. If something is removed, naturally fill the exposed area by matching the surrounding original background, texture, lighting, and shadows. Never use a transparent background, checkerboard background, blank canvas, new scene, new camera angle, redesign, or unrelated props. Do not add or remove text unless explicitly requested.\\n\\nORIGINAL PROMPT (keep only details compatible with the local edit):\\n'+base+'\\n\\nReturn the same original scene with only the requested local modification.';
    const previousText=textarea?.value;job.prompts[index].prompt=composed;job.prompts[index].regenDirection=direction;if(textarea)textarea.value=composed;
    try{await baseRegen(index)}finally{job.prompts[index].prompt=base;if(textarea)textarea.value=previousText;await saveHistory(job)}
  };
  window.regen=async(index,direction)=>direction?runWithDirection(index,String(direction).trim()):open(index);
  confirm.onclick=async()=>{const direction=input.value.trim(),index=targetIndex;if(index<0)return;confirm.disabled=true;confirm.textContent='生成中…';try{close();if(direction)await runWithDirection(index,direction);else await baseRegen(index)}catch(error){log(error.message);targetIndex=index;modal.classList.remove('hidden')}finally{confirm.disabled=false;confirm.textContent='按此方向重新生成'}};
  const style=document.createElement('style');style.textContent='.regen-direction-modal{position:fixed;inset:0;z-index:80;background:rgba(15,23,42,.42);display:grid;place-items:center;padding:20px}.regen-direction-dialog{width:min(620px,100%);background:#fff;border:1px solid var(--line);border-radius:16px;box-shadow:0 24px 70px rgba(15,23,42,.25);padding:20px}.regen-direction-head{display:flex;justify-content:space-between;align-items:flex-start}.regen-direction-head strong{display:block;font-size:16px}.regen-direction-head span{display:block;margin-top:5px;color:var(--muted);font-size:12px}.regen-direction-note{margin:16px 0 10px;color:#526074;font-size:12px;line-height:1.6}.regen-direction-chips{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:10px}.regen-direction-chips button{border:1px solid #d9e1ef;background:#f8faff;color:#405574;border-radius:99px;padding:6px 10px;font-size:11px}.regen-direction-chips button:hover{border-color:var(--blue);color:var(--blue);background:#f1f4ff}.regen-direction-dialog textarea{min-height:128px;font-size:13px}.regen-direction-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:13px}.regen-direction-actions button{font-size:12px}.regen-direction-modal.hidden{display:none!important}@media(max-width:650px){.regen-direction-dialog{padding:16px}.regen-direction-chips button{font-size:10px}}';document.head.appendChild(style);
};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else install();
})();</script>'''
HTML=HTML.replace('</body></html>',HTML_REGEN_DIRECTION_FIX+'</body></html>')
HTML_IMAGE_REFRESH_FIX='''<script>(()=>{
const install=()=>{
  const original=window.renderResults;
  if(typeof original!=='function'||original.__watchStudioCacheBust)return;
  const refresh=()=>{
    document.querySelectorAll('#resultGrid .result-media img').forEach((img,index)=>{
      const item=typeof current!=='undefined' ? current?.results?.[index] : null;
      const url=item?.url;
      const version=item?.updatedAt||item?.version;
      if(!url||!version)return;
      const next=url+(url.includes('?')?'&':'?')+'v='+encodeURIComponent(version);
      const absolute=new URL(next,window.location.href).href;
      if(img.src!==absolute)img.src=next;
    });
  };
  const wrapped=function(){const result=original.apply(this,arguments);refresh();return result};
  wrapped.__watchStudioCacheBust=true;
  window.renderResults=wrapped;
};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else install();
})();</script>'''
HTML=HTML.replace('</body></html>',HTML_IMAGE_REFRESH_FIX+'</body></html>')
HTML_RESULT_VERSION_FIX='''<script>(()=>{
const install=()=>{
  const original=window.renderResults;
  if(typeof original!=='function'||original.__watchStudioVersions)return;
  const decorate=()=>{
    document.querySelectorAll('#resultGrid .result-card').forEach((card,index)=>{
      const item=typeof current!=='undefined' ? current?.results?.[index] : null;
      const versions=Array.isArray(item?.versions)?item.versions.filter(version=>version&&version.url):[];
      const media=card.querySelector('.result-media');
      const meta=card.querySelector('.result-meta');
      if(!media||!meta)return;
      let nav=meta.querySelector('.version-nav');
      if(versions.length<2){nav?.remove();return}
      const active=Math.max(0,Math.min(Number.isInteger(item.activeVersion)?item.activeVersion:versions.length-1,versions.length-1));
      if(!nav){nav=document.createElement('div');nav.className='version-nav';const actions=meta.querySelector('.result-actions');actions?meta.insertBefore(nav,actions):meta.appendChild(nav)}
      nav.innerHTML='<button type="button" data-version-prev aria-label="查看上一版">‹</button><span>第 '+(active+1)+' / '+versions.length+' 版</span><button type="button" data-version-next aria-label="查看下一版">›</button>';
      nav.querySelector('[data-version-prev]').disabled=active<=0;
      nav.querySelector('[data-version-next]').disabled=active>=versions.length-1;
      nav.querySelector('[data-version-prev]').onclick=event=>{event.stopPropagation();window.switchResultVersion(index,-1)};
      nav.querySelector('[data-version-next]').onclick=event=>{event.stopPropagation();window.switchResultVersion(index,1)};
    });
  };
  const wrapped=function(){const result=original.apply(this,arguments);decorate();return result};
  wrapped.__watchStudioVersions=true;
  window.renderResults=wrapped;
  window.switchResultVersion=(index,delta)=>{
    const slot=typeof current!=='undefined' ? current?.results?.[index] : null;
    const versions=Array.isArray(slot?.versions)?slot.versions.filter(version=>version&&version.url):[];
    if(!slot||versions.length<2)return;
    const active=Math.max(0,Math.min(Number.isInteger(slot.activeVersion)?slot.activeVersion:versions.length-1,versions.length-1));
    const next=active+delta;if(next<0||next>=versions.length)return;
    const version=versions[next];slot.versions=versions;slot.activeVersion=next;slot.url=version.url;slot.sourceUrl=version.sourceUrl||'';slot.updatedAt=version.updatedAt||String(Date.now());slot.status='success';slot.error='';
    renderResults();saveHistory(current).catch(error=>log('保存图片版本失败：'+error.message));
  };
  const style=document.createElement('style');style.textContent='.version-nav{display:flex;justify-content:center;align-items:center;gap:10px;margin:8px 0 0}.version-nav button{width:30px;height:25px;border:1px solid #dfe4ec;border-radius:7px;background:#f5f7fb;color:#344054;font-size:18px;line-height:1;padding:0}.version-nav button:hover:not(:disabled){border-color:var(--blue);color:var(--blue);background:#f1f4ff}.version-nav button:disabled{opacity:.35;cursor:default}.version-nav span{color:var(--muted);font-size:10px}';document.head.appendChild(style);
};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else install();
})();</script>'''
HTML=HTML.replace('</body></html>',HTML_RESULT_VERSION_FIX+'''<script>
(()=>{const style=document.createElement('style');style.textContent='.image-preview{position:fixed;inset:0;z-index:1000;background:rgba(9,14,25,.88);display:none;align-items:center;justify-content:center;padding:4vh 4vw;cursor:zoom-out;overflow:hidden;touch-action:none}.image-preview.open{display:flex}.image-preview img{max-width:92vw;max-height:92vh;object-fit:contain;border-radius:8px;box-shadow:0 12px 50px rgba(0,0,0,.35);transform:translate(0px,0px) scale(1);transform-origin:center center;cursor:zoom-in;user-select:none;-webkit-user-drag:none;touch-action:none}.image-preview.zoomed img{cursor:grab}.image-preview.dragging img{cursor:grabbing}.image-preview button{position:absolute;right:22px;top:18px;z-index:2;width:42px;height:42px;border-radius:50%;background:#fff;color:#17202f;font-size:26px;line-height:1}.thumb img{pointer-events:auto;cursor:zoom-in}.result-media img,.history-item img{cursor:zoom-in}';document.head.appendChild(style);const preview=document.createElement('div');preview.className='image-preview';preview.setAttribute('role','dialog');preview.setAttribute('aria-label','图片预览');preview.innerHTML='<button type="button" aria-label="关闭图片预览">×</button><img alt="图片放大预览">';document.body.appendChild(preview);const image=preview.querySelector('img');let scale=1,dx=0,dy=0,drag=null;function draw(){image.style.transform='translate('+dx+'px,'+dy+'px) scale('+scale+')';preview.classList.toggle('zoomed',scale>1);preview.classList.toggle('dragging',!!drag)}function close(){preview.classList.remove('open');image.removeAttribute('src');scale=1;dx=dy=0;drag=null;draw()}preview.addEventListener('click',close);preview.querySelector('button').addEventListener('click',close);image.addEventListener('click',event=>event.stopPropagation());preview.addEventListener('wheel',event=>{if(!preview.classList.contains('open'))return;event.preventDefault();const rect=preview.getBoundingClientRect(),mx=event.clientX-(rect.left+rect.width/2),my=event.clientY-(rect.top+rect.height/2),next=Math.max(1,Math.min(8,scale*Math.exp(-event.deltaY*.001)));dx=mx-(mx-dx)*(next/scale);dy=my-(my-dy)*(next/scale);scale=next;draw()},{passive:false});image.addEventListener('pointerdown',event=>{if(scale<=1)return;event.preventDefault();drag={x:event.clientX,y:event.clientY,dx,dy};image.setPointerCapture(event.pointerId);draw()});image.addEventListener('pointermove',event=>{if(!drag)return;dx=drag.dx+event.clientX-drag.x;dy=drag.dy+event.clientY-drag.y;draw()});function endDrag(){if(drag){drag=null;draw()}}image.addEventListener('pointerup',endDrag);image.addEventListener('pointercancel',endDrag);document.addEventListener('keydown',event=>{if(event.key==='Escape')close()});document.addEventListener('click',event=>{const target=event.target.closest('.thumb img,.result-media img,.history-item img');if(!target)return;event.stopPropagation();scale=1;dx=dy=0;drag=null;image.src=target.dataset.full||target.currentSrc||target.src;draw();preview.classList.add('open')})})();
</script></body></html>''')
HTML=HTML.replace("am.value='gpt-5.6-terra'","am.value='gpt-5.6-sol'").replace("analysisModel.value='gpt-5.6-terra'","analysisModel.value='gpt-5.6-sol'").replace('GPT-5.6 Terra 正在分析','GPT-5.6 Sol 正在分析')
HTML=HTML.replace('提示词收藏','提示词模板库').replace('收藏当前提示词','保存当前模板').replace('收藏提示词','提示词模板').replace('已载入提示词模板','已载入提示词模板').replace('已载入收藏提示词','已载入提示词模板').replace('自定义提示词已收藏','自定义提示词模板已保存').replace('收藏提示词已更新','提示词模板已更新').replace('收藏于 ','保存于 ')
if AUTH_ENABLED:HTML=HTML.replace('</body></html>','''<script>(()=>{const top=document.querySelector('.top-actions');if(!top)return;const button=document.createElement('button');button.type='button';button.className='secondary';button.textContent='退出登录';button.onclick=async()=>{await fetch('/studio/logout',{method:'POST'});location.replace('/studio/')};top.appendChild(button)})();</script></body></html>''')
HTML_MODE_COUNT_FIX='''<style>.top-actions #keyBtn{display:none!important}</style><script>(()=>{document.getElementById('keyBtn')?.remove();const mode=document.getElementById('mode'),count=document.getElementById('count');if(!mode||!count)return;const sync=()=>document.getElementById('analyzeModel')?.closest('.build-section')?.classList.toggle('hidden',mode.value==='prompt');mode.addEventListener('change',()=>{if(mode.value==='prompt')count.value='1';sync()});count.addEventListener('change',sync);sync()})();</script>'''
HTML=HTML.replace('</body></html>',HTML_MODE_COUNT_FIX+'</body></html>')

LOGIN_HTML = r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>登录 · Watch Studio</title><style>
:root{font-family:Inter,-apple-system,BlinkMacSystemFont,"PingFang SC","Segoe UI",sans-serif;color:#202938;background:#f3f5f8}*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;padding:24px;background:linear-gradient(135deg,#f5f7fa,#edf1f6)}.login{width:min(100%,400px);background:#fff;border:1px solid #e1e6ed;border-radius:12px;padding:32px;box-shadow:0 18px 55px rgba(25,39,60,.09)}.brand{display:flex;align-items:center;gap:12px;margin-bottom:30px}.mark{width:42px;height:42px;border-radius:11px;background:#315efb;color:white;display:grid;place-items:center;font-weight:800;font-size:18px}.brand strong{font-size:15px;display:block}.brand span{display:block;color:#7b8797;font-size:12px;margin-top:3px}.title{margin:0 0 7px;font-size:23px;font-weight:680;letter-spacing:0}.hint{margin:0 0 24px;color:#707c8d;font-size:13px}.field{margin:17px 0}.field label{display:block;font-size:12px;font-weight:650;margin:0 0 8px;color:#485466}.field input{width:100%;height:44px;border:1px solid #d8dee7;border-radius:7px;padding:0 12px;font:inherit;color:#202938;background:#fff;outline:none}.field input:focus{border-color:#5e7ef5;box-shadow:0 0 0 3px #e9eeff}.submit{height:44px;width:100%;margin-top:8px;border:0;border-radius:7px;background:#315efb;color:#fff;font:inherit;font-size:14px;font-weight:600;cursor:pointer}.submit:hover{background:#244de0}.error{padding:10px 12px;border:1px solid #f2c9c9;border-radius:7px;background:#fff5f4;color:#a63e39;font-size:13px;margin:0 0 16px}.foot{margin-top:22px;text-align:center;color:#98a1ae;font-size:11px}@media(max-width:420px){.login{padding:25px 22px}}
</style></head><body><main class="login"><div class="brand"><div class="mark">W</div><div><strong>Watch Studio</strong><span>账号安全登录</span></div></div><h1 class="title">欢迎回来</h1><p class="hint">登录以继续使用工作台</p>{{ERROR}}<form method="post" action="/studio/login" autocomplete="on"><div class="field"><label for="username">账号</label><input id="username" name="username" autocomplete="username" required autofocus></div><div class="field"><label for="password">密码</label><input id="password" name="password" type="password" autocomplete="current-password" required></div><button class="submit" type="submit">登录</button></form><div class="foot">Watch Studio</div></main></body></html>'''

def render_login(error=False):
    message='<div class="error" role="alert">账号或密码不正确，请重试。</div>' if error else ''
    return LOGIN_HTML.replace('{{ERROR}}',message).encode()

def json_response(h, status, payload):
    data=json.dumps(payload,ensure_ascii=False).encode();h.send_response(status);h.send_header('Content-Type','application/json; charset=utf-8');h.send_header('Content-Length',str(len(data)));h.end_headers();h.wfile.write(data)
def read_json(h):
    n=int(h.headers.get('Content-Length','0'));return json.loads(h.rfile.read(n).decode()) if n else {}
def key_store():
    try:return json.loads(KEYS.read_text())
    except:return {}
def valid_key(k):
    if not k or any(c.isspace() for c in k):raise ValueError('API Key 为空或格式不正确')
def extract_url(v):
    if isinstance(v,str) and v.startswith(('http://','https://','data:image/')):return v
    if isinstance(v,dict):
        for x in v.values():
            u=extract_url(x)
            if u:return u
    if isinstance(v,list):
        for x in v:
            u=extract_url(x)
            if u:return u
    return ''
def extract_id(v):
    if isinstance(v,dict):
        for k in ('id','task_id','taskId','key'):
            if v.get(k):return str(v[k])
        for k in ('data','result','task'):
            x=extract_id(v.get(k))
            if x:return x
    return ''
def extract_b64(v):
    if isinstance(v,dict):
        for k in ('b64_json','b64','base64'):
            if isinstance(v.get(k),str) and v[k].strip():
                return 'data:image/png;base64,'+v[k].strip()
        for x in v.values():
            r=extract_b64(x)
            if r:return r
    if isinstance(v,list):
        for x in v:
            r=extract_b64(x)
            if r:return r
    return ''
def local_image_data(url):
    text=str(url or '')
    name=text.split('/uploads/',1)[1].split('?',1)[0] if '/uploads/' in text else ''
    path=(UPLOADS/name).resolve() if name else None
    if not path or path.parent != UPLOADS.resolve() or not path.exists(): return text
    mime=mimetypes.guess_type(path.name)[0] or 'image/jpeg'
    return f'data:{mime};base64,'+base64.b64encode(path.read_bytes()).decode()
def prepare_api_body(body):
    out=json.loads(json.dumps(body))
    # HFSY GPT Image accepts reference-image URLs but explicitly rejects Base64.
    # Uploaded images therefore remain public URLs here. Gemini keeps its own
    # inline-data conversion below when that format is required.
    if isinstance(out.get('reference_images'),list):
        local_refs=[str(url) for url in out['reference_images'] if str(url).startswith('/uploads/')]
        if local_refs: raise ValueError('参考图尚未上传到公网服务器，请重新上传后再生成')
        out['reference_images']=[upstream_image_url(url) for url in out['reference_images']]
    for content in out.get('contents',[]) if isinstance(out.get('contents'),list) else []:
        for part in content.get('parts',[]) if isinstance(content,dict) else []:
            file_data=part.get('fileData') if isinstance(part,dict) else None
            if isinstance(file_data,dict) and file_data.get('fileUri'):
                file_data['fileUri']=upstream_image_url(file_data['fileUri'])
            if isinstance(file_data,dict) and file_data.get('fileUri','').startswith('/uploads/'):
                data=local_image_data(file_data['fileUri']);mime=file_data.get('mimeType') or 'image/jpeg'
                if data.startswith('data:'): part.pop('fileData',None);part['inlineData']={'mimeType':mime,'data':data.split(',',1)[1]}
    return out
RETRYABLE={429,500,502,503,504}
ANALYZE_SEM=threading.BoundedSemaphore(1)
DIRECT_OPENER=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def is_reference_fetch_error(payload):
    """Only retry transient upstream failures while it downloads our reference URL."""
    try: text=json.dumps(payload,ensure_ascii=False).lower()
    except Exception: text=str(payload).lower()
    markers=('image_url fetch failed','unable to download content from the provided url','error while downloading file','failed to download image','reference image download')
    return any(marker in text for marker in markers)
def is_transient_analysis_failure(status,payload):
    """Failures for which a second configured analysis provider is safe to try."""
    if status in RETRYABLE:
        return True
    try: text=json.dumps(payload,ensure_ascii=False).lower()
    except Exception: text=str(payload).lower()
    markers=(
        'upstream service is temporarily unavailable',
        'upstream stream ended without a terminal response event',
        'timed out', 'timeout', 'connection reset', 'connection aborted',
    )
    return any(marker in text for marker in markers)
def analysis_fallbacks(selected,store):
    """Yield only other providers that actually have a server-side key."""
    for upstream in ANALYSIS_UPSTREAMS:
        if upstream == selected:
            continue
        key=str(store.get(f'analysis_{upstream}') or (store.get('analysis') if upstream=='owlai' else '') or '').strip()
        if key:
            yield upstream,key

_PROMPT_NUMBER_LABEL_RE=re.compile(r'(?i)(?:提示词|详情图)\s*(?:#|编号|no\.?)?\s*\d+\s*(?:[|｜:：.\-]\s*)?')
_PROMPT_NUMBER_PREFIX_RE=re.compile(r'(?im)^\s*(?:prompt\s*(?:#|编号|no\.?)?\s*\d+|\d+\s*[.)、:：\-])\s*(?:[|｜:：.\-]\s*)?')
def strip_prompt_number_label(value):
    """Remove planning-only numbered labels before the image model sees a prompt."""
    text=str(value or '').strip()
    if not text:return ''
    text=_PROMPT_NUMBER_LABEL_RE.sub('',text)
    text=_PROMPT_NUMBER_PREFIX_RE.sub('',text)
    return re.sub(r'[ \t]{2,}',' ',text).strip()
def _compact_analysis_data_url(value,max_side=1400,quality=65):
    """Downsize one inline analysis image without touching the original upload."""
    text=str(value or '')
    if not text.startswith('data:') or ',' not in text:return text
    try:
        _,encoded=text.split(',',1);raw=base64.b64decode(encoded,validate=False)
        with tempfile.TemporaryDirectory(prefix='watch-analysis-') as folder:
            source=pathlib.Path(folder)/'source.bin';target=pathlib.Path(folder)/'compact.jpg';source.write_bytes(raw)
            result=subprocess.run(['/usr/bin/sips','-Z',str(max_side),'-s','format','jpeg','-s','formatOptions',str(quality),str(source),'--out',str(target)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
            if result.returncode!=0 or not target.exists():return text
            compact=target.read_bytes()
        return 'data:image/jpeg;base64,'+base64.b64encode(compact).decode()
    except Exception as error:
        print(f'[analysis] 压缩参考图失败，继续使用原图：{error}',flush=True)
        return text
def compact_analysis_request(request):
    """Return a request with inline reference images compressed for a retry."""
    try: compact=json.loads(json.dumps(request,ensure_ascii=False))
    except Exception:return request,False,0,0
    before=0;after=0;changed=False
    def visit(node):
        nonlocal before,after,changed
        if isinstance(node,dict):
            image=node.get('image_url')
            if isinstance(image,dict) and isinstance(image.get('url'),str) and image['url'].startswith('data:'):
                original=image['url'];compressed=_compact_analysis_data_url(original)
                before+=len(original);after+=len(compressed)
                if compressed!=original:image['url']=compressed;changed=True
            for child in node.values():visit(child)
        elif isinstance(node,list):
            for child in node:visit(child)
    visit(compact)
    return compact,changed,before,after
def analysis_request_is_large(request,limit=4*1024*1024):
    try:return len(json.dumps(request,ensure_ascii=False).encode())>limit
    except Exception:return False
def analysis_payload_is_too_large(status,payload):
    if status==413:return True
    try:text=json.dumps(payload,ensure_ascii=False).lower()
    except Exception:text=str(payload).lower()
    return any(marker in text for marker in ('request entity too large','request body too large','payload too large','413 request','content length too large'))
_NO_OVERLAY_TEXT_RE=re.compile(r'(不要.{0,8}(文字|文本|字样|文案)|不加.{0,8}(文字|文本|字样|文案)|无文字|不要出现.{0,8}(文字|文本)|禁止.{0,8}(文字|文本|文案)|no\s+(visible\s+)?text|no\s+typography|no\s+lettering|no\s+captions|no\s+words|without\s+(adding\s+)?(any\s+)?(text|lettering|words)|text[- ]free|do\s+not\s+(add|include|render|show).*\b(text|lettering|words|captions|typography)\b|don.t\s+(add|include|render|show).*\b(text|lettering|words|captions|typography)\b)',re.I)
def requests_no_overlay_text(*values):
    return any(_NO_OVERLAY_TEXT_RE.search(str(value or '')) for value in values)
def normalize_analysis_plan(payload,count,no_overlay_text=False):
    """Validate and normalize an analysis response before any image requests start."""
    content=payload.get('choices',[{}])[0].get('message',{}).get('content','') if isinstance(payload,dict) else ''
    data=json.loads(content) if isinstance(content,str) else content
    if not isinstance(data,dict): raise ValueError('分析上游没有返回 JSON 对象')
    normalized=[]
    for raw_index,item in enumerate(data.get('prompts') or [],1):
        if not isinstance(item,dict):
            print(f'[analyze] 跳过非对象提示词 #{raw_index}',flush=True);continue
        def value(*keys): return next((str(item.get(key) or '').strip() for key in keys if str(item.get(key) or '').strip()),'')
        prompt_value=strip_prompt_number_label(value('prompt','image_prompt','imagePrompt','prompt_en','text_prompt','description'))
        if not prompt_value:
            print(f'[analyze] 跳过缺少生图提示字段的对象 #{raw_index}: keys={list(item.keys())[:12]}',flush=True);continue
        title=strip_prompt_number_label(value('title','name','headline')) or f'Product Detail {len(normalized)+1}'
        purpose=value('purpose','objective','goal') or 'Product detail image'
        camera=value('camera_angle','cameraAngle','camera','angle') or 'Product-led editorial composition'
        scene=value('scene','scene_description','setting','environment') or 'Premium product-detail setting'
        copy='' if no_overlay_text else (strip_prompt_number_label(value('on_image_copy','onImageCopy','copy','text_overlay','headline_copy')) or 'DISCOVER THE DETAILS')
        item={'title':title,'purpose':purpose,'camera_angle':camera,'scene':scene,'on_image_copy':copy,'prompt':prompt_value}
        if no_overlay_text:
            item['prompt']+=' Do not add any overlay text, captions, headline, callout, logo, watermark, or graphic lettering anywhere in the image. Preserve only authentic details physically present on the reference product itself, such as its original dial markings and logo.'
        elif copy.lower() not in item['prompt'].lower():
            item['prompt']+=f' Render this exact visible English ecommerce copy, with no placeholders: "{copy}". Make the headline, subhead and callouts legible in a premium editorial hierarchy with deliberate whitespace.'
        normalized.append(item)
    if len(normalized)<count: raise ValueError(f'分析结果中可用提示词不足：需要 {count} 条，实际识别到 {len(normalized)} 条')
    if len(normalized)>count:
        print(f'[analyze] 上游返回 {len(normalized)} 条可用提示词，按本次出图数量截取前 {count} 条',flush=True)
        normalized=normalized[:count]
    return data,normalized
def run_parallel_analysis(request,count,store,client_ip='',no_overlay_text=False):
    """Race both fixed analysis providers; retry each failed provider every 5 seconds."""
    providers=[]
    for upstream in ('owlai','tyai'):
        key=str(store.get(f'analysis_{upstream}') or (store.get('analysis') if upstream=='owlai' else '') or '').strip()
        if key: providers.append((upstream,key))
    if not providers: raise ValueError('OwlAI 和 TyAI 都没有配置分析 Key')
    deadline=time.monotonic()+420
    stop=threading.Event();events=queue.Queue();workers=[]
    def worker(upstream,key):
        attempts=0;compacted_request=request;compacted=False
        models=('gpt-6.1-sol','gpt-6-sol') if upstream=='tyai' else (str(request.get('model') or 'gpt-5.6-sol'),)
        model_index=0
        while not stop.is_set() and time.monotonic()<deadline:
            attempts+=1;remaining=max(1,deadline-time.monotonic())
            request_for_attempt=json.loads(json.dumps(compacted_request,ensure_ascii=False))
            request_for_attempt['model']=models[model_index]
            try:
                status,payload=proxy('/v1/chat/completions',key,request_for_attempt,retries=0,timeout=remaining,base=ANALYSIS_UPSTREAMS[upstream])
                if status<400:
                    try:
                        data,normalized=normalize_analysis_plan(payload,count,no_overlay_text)
                        if not stop.is_set():
                            print(f'[analysis-race] {upstream} model={models[model_index]} 第 {attempts} 次返回可用提示词 {len(normalized)} 条',flush=True)
                            events.put(('success',upstream,data,normalized));stop.set();return
                    except Exception as error:
                        print(f'[analysis-race] {upstream} model={models[model_index]} 第 {attempts} 次返回不可用：{error}',flush=True)
                        model_index=(model_index+1)%len(models)
                else:
                    print(f'[analysis-race] {upstream} model={models[model_index]} 第 {attempts} 次错误 HTTP {status}：{str(payload)[:220]}',flush=True)
                    too_large=analysis_payload_is_too_large(status,payload)
                    try:error_text=json.dumps(payload,ensure_ascii=False).lower()
                    except Exception:error_text=str(payload).lower()
                    oversized_timeout=analysis_request_is_large(request_for_attempt) and 'timed out' in error_text
                    if (too_large or oversized_timeout) and not compacted:
                        compacted_request,changed,before,after=compact_analysis_request(compacted_request)
                        if changed:
                            compacted=True
                            print(f'[analysis-race] {upstream} 请求体过大，已压缩分析参考图后立即重试（图片数据 {before//1024}KB -> {after//1024}KB）',flush=True)
                            continue
                    model_index=(model_index+1)%len(models)
            except Exception as error:
                print(f'[analysis-race] {upstream} model={models[model_index]} 第 {attempts} 次请求异常：{str(error)[:220]}',flush=True)
                if not compacted and analysis_request_is_large(request_for_attempt) and 'timed out' in str(error).lower():
                    compacted_request,changed,before,after=compact_analysis_request(compacted_request)
                    if changed:
                        compacted=True
                        print(f'[analysis-race] {upstream} 大请求超时，已压缩分析参考图后立即重试（图片数据 {before//1024}KB -> {after//1024}KB）',flush=True)
                        continue
                model_index=(model_index+1)%len(models)
            if stop.is_set():return
            remaining=deadline-time.monotonic()
            if remaining<=0:break
            stop.wait(min(5,remaining))
        events.put(('failed',upstream,f'{upstream} 在 7 分钟内未返回可用提示词',None))
    for upstream,key in providers:
        thread=threading.Thread(target=worker,args=(upstream,key),daemon=True);thread.start();workers.append(thread)
    failed=0;last_error=''
    while time.monotonic()<deadline and failed<len(providers):
        try:result=events.get(timeout=min(1,max(.1,deadline-time.monotonic())))
        except queue.Empty:continue
        if result[0]=='success':return result[2],result[3],result[1]
        failed+=1;last_error=result[2]
    stop.set()
    raise TimeoutError(last_error or 'OwlAI 和 TyAI 在 7 分钟内均未返回可用提示词')
def direct_open(request,timeout):
    return DIRECT_OPENER.open(request,timeout=timeout)
def proxy(path,key,payload=None,method='POST',retries=2,timeout=300,base=None):
    base=base or API_BASE;url=base+path
    for attempt in range(retries+1):
        data=None if method=='GET' else json.dumps(payload or {},ensure_ascii=False).encode()
        req=urllib.request.Request(url,data=data,method=method,headers={'Content-Type':'application/json','Accept':'application/json','Authorization':f'Bearer {key}','User-Agent':'WatchStudio/1.0'})
        try:
            with direct_open(req,timeout=timeout) as r:
                raw=r.read().decode('utf-8','replace');return r.status,json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            raw=e.read().decode('utf-8','replace');
            try:j=json.loads(raw)
            except:j={'raw':raw}
            if e.code in RETRYABLE and attempt<retries:
                print(f'upstream {e.code} for {path}, retry {attempt+1}/{retries}',flush=True)
                time.sleep(15*(attempt+1) if e.code==429 else 2+attempt*3);continue
            return e.code,j
        except urllib.error.URLError as e:
            if attempt<retries:
                print(f'upstream network error for {path}, retry {attempt+1}/{retries}: {str(e)[:120]}',flush=True)
                time.sleep(2+attempt*3);continue
            return 502,{'error':{'message':str(e)}}
        except Exception as e:
            if attempt<retries:
                print(f'upstream connection interrupted for {path}, retry {attempt+1}/{retries}: {str(e)[:120]}',flush=True)
                time.sleep(2+attempt*3);continue
            return 502,{'error':{'message':f'上游连接中断：{e}'}}
HISTORY_MAX=500;_HIST=[];_HIST_GID={}
def _history_flush():
    DATA.mkdir(exist_ok=True);tmp=HISTORY.with_name(HISTORY.name+'.tmp')
    with tmp.open('w',encoding='utf-8') as f:
        for r in _HIST:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    os.replace(tmp,HISTORY)
def prompt_favorites():
    if not PROMPT_FAVORITES.exists(): return []
    try:
        values=json.loads(PROMPT_FAVORITES.read_text(encoding='utf-8'))
        return values if isinstance(values,list) else []
    except Exception:return []
def write_prompt_favorites(values):
    DATA.mkdir(exist_ok=True)
    tmp=PROMPT_FAVORITES.with_name(PROMPT_FAVORITES.name+'.tmp')
    tmp.write_text(json.dumps(values,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(tmp,PROMPT_FAVORITES)
    PROMPT_FAVORITES.chmod(0o600)
def _history_load():
    if not HISTORY.exists():return
    for line in HISTORY.read_text(encoding='utf-8').splitlines():
        try:r=json.loads(line)
        except:continue
        history_merge(r,flush=False)
    interrupted=False
    migrated_versions=False
    output_root=OUTPUTS.resolve()
    for record in _HIST:
        for item in record.get('results') or []:
            if not isinstance(item,dict) or item.get('updatedAt') or not str(item.get('url') or '').startswith('/outputs/'):
                continue
            relative=urllib.parse.unquote(str(item.get('url')).split('/outputs/',1)[1].split('?',1)[0])
            candidate=(OUTPUTS/relative).resolve()
            if output_root in candidate.parents and candidate.is_file():
                item['updatedAt']=str(candidate.stat().st_mtime_ns)
                migrated_versions=True
    for record in _HIST:
        if str(record.get('status') or '') in ('analyzing','queued','creating','generating','polling'):
            record['status']='failed';record['error']='服务重启导致原后台任务中断，请重新创建任务';record['updatedAt']=time.strftime('%Y-%m-%dT%H:%M:%S');interrupted=True
    if interrupted or migrated_versions or _HIST:
        # Persist normalized prompt metadata too, so a reload cannot restore
        # old numbered labels such as "详情图 1" into the next generation.
        _history_flush()
def history_merge(record,flush=True):
    global _HIST,_HIST_GID
    if not isinstance(record,dict) or not record:return
    for item in record.get('prompts') or []:
        if not isinstance(item,dict):continue
        if 'prompt' in item:item['prompt']=strip_prompt_number_label(item.get('prompt'))
        if 'title' in item:item['title']=strip_prompt_number_label(item.get('title')) or 'Product Detail'
        if 'on_image_copy' in item:item['on_image_copy']=strip_prompt_number_label(item.get('on_image_copy'))
    with FILE_LOCK:
        gid=str(record.get('generationId') or '')
        if gid and gid in _HIST_GID:
            old=_HIST[_HIST_GID[gid]]
            old_res=old.get('results') if isinstance(old.get('results'),list) else []
            new_res=record.get('results') if isinstance(record.get('results'),list) else []
            merged=[]
            for idx in range(max(len(old_res),len(new_res))):
                o=old_res[idx] if idx<len(old_res) else None
                n=new_res[idx] if idx<len(new_res) else None
                if isinstance(n,dict):
                    if isinstance(o,dict):
                        try:n_revision=int(str(n.get('updatedAt') or 0))
                        except (TypeError,ValueError):n_revision=0
                        try:o_revision=int(str(o.get('updatedAt') or 0))
                        except (TypeError,ValueError):o_revision=0
                        # Full-record browser saves can arrive out of order while
                        # other images are generating. Keep each slot's newest state.
                        chosen=n if n_revision>=o_revision else o
                        if chosen is n:
                            for key in ('versions','activeVersion','sourceUrl','taskId','previousUrl'):
                                if key not in n and key in o:n[key]=o[key]
                        merged.append(chosen)
                    else:merged.append(n)
                elif isinstance(o,dict):merged.append(o)
                else:merged.append({'status':'queued','url':''})
            record['results']=merged
            for f in ('selling_points_cn','prompts','images','userPrompt','model','aspect','status','error','analysisUpstreamUsed'):
                if not record.get(f) and old.get(f):record[f]=old[f]
            _HIST[_HIST_GID[gid]]=record
        else:
            if gid:_HIST_GID[gid]=len(_HIST)
            _HIST.append(record)
        if len(_HIST)>HISTORY_MAX:
            _HIST.pop(0);_HIST_GID={str(r.get('generationId') or ''):i for i,r in enumerate(_HIST) if r.get('generationId')}
        if flush:_history_flush()
def history_update_result(generation_id,index,result):
    gid=str(generation_id or '')
    if not gid or int(index or 0)<1:return
    with FILE_LOCK:
        i=_HIST_GID.get(gid)
        if i is None:return
        rec=_HIST[i];rec.setdefault('results',[])
        while len(rec['results'])<int(index):rec['results'].append({'status':'queued','url':''})
        prior=rec['results'][int(index)-1] if isinstance(rec['results'][int(index)-1],dict) else {}
        result={**prior,**dict(result or {})}
        result['updatedAt']=str(time.time_ns())
        rec['results'][int(index)-1]=result
        if rec['results'] and all(isinstance(item,dict) and item.get('url') for item in rec['results']):
            rec['status']='completed'
        rec['updatedAt']=time.strftime('%Y-%m-%dT%H:%M:%S')
        _history_flush()
def history_update_state(generation_id,status,error='',failure_stage=''):
    gid=str(generation_id or '')
    with FILE_LOCK:
        i=_HIST_GID.get(gid)
        if i is None:return
        rec=_HIST[i];rec['status']=status;rec['updatedAt']=time.strftime('%Y-%m-%dT%H:%M:%S')
        if error:rec['error']=str(error)
        if failure_stage:rec['failureStage']=failure_stage
        _history_flush()
def history_update_meta(generation_id,**fields):
    gid=str(generation_id or '')
    with FILE_LOCK:
        i=_HIST_GID.get(gid)
        if i is None:return
        _HIST[i].update({key:value for key,value in fields.items() if value is not None})
        _HIST[i]['updatedAt']=time.strftime('%Y-%m-%dT%H:%M:%S');_history_flush()
def history_remove_failed(scope='failed_without_images'):
    global _HIST,_HIST_GID
    with FILE_LOCK:
        removed=[];kept=[]
        for record in _HIST:
            has_image=any(isinstance(item,dict) and item.get('url') for item in record.get('results') or [])
            is_failed=str(record.get('status') or '')=='failed'
            should_remove=is_failed and (scope=='all_failed' or not has_image)
            if should_remove: removed.append(record)
            else: kept.append(record)
        _HIST=kept;_HIST_GID={str(record.get('generationId') or ''):index for index,record in enumerate(_HIST) if record.get('generationId')}
        _history_flush()
        return removed
def history_ensure(record):
    if not isinstance(record,dict) or not record:return
    gid=str(record.get('generationId') or '')
    with FILE_LOCK:
        if not gid or gid in _HIST_GID:return
        _HIST_GID[gid]=len(_HIST);_HIST.append(record);_history_flush()
def history_records():
    with FILE_LOCK:snap=list(_HIST)
    out=[]
    for record in reversed(snap):
        item=dict(record);results=item.get('results') if isinstance(item.get('results'),list) else []
        if results and all(isinstance(result,dict) and result.get('url') for result in results): item['status']='completed'
        out.append(item)
    return out
def internal_post(path,payload,timeout=900):
    req=urllib.request.Request(f'http://127.0.0.1:{PORT}{path}',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Content-Type':'application/json','User-Agent':'WatchStudio-Worker/1.0'})
    try:
        with direct_open(req,timeout=timeout) as response:
            raw=response.read().decode('utf-8','replace');return response.status,json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        raw=error.read().decode('utf-8','replace')
        try:return error.code,json.loads(raw)
        except:return error.code,{'error':raw}
    except Exception as error:return 502,{'error':str(error)}
def image_request_body(model,prompt,images,aspect):
    prompt=strip_prompt_number_label(prompt)
    if model in ('nano-banana-2','gemini-3.1-flash-image-preview'):
        return {'endpoint':f'/v1beta/models/{model}:generateContent','model':model,'contents':[{'parts':[{'text':prompt},*({'fileData':{'mimeType':'image/jpeg','fileUri':url}} for url in images)]}],'generationConfig':{'imageConfig':{'aspectRatio':aspect}},'async':True,'background':True}
    sizes={'1:1':'1024x1024','4:5':'832x1040','3:4':'768x1024','16:9':'1280x720','9:16':'720x1280','4:3':'1024x768'}
    return {'endpoint':'/v1/images/generations','model':model,'prompt':prompt,'size':sizes.get(aspect,'1024x1024'),'reference_images':images,'n':1,'response_format':'b64_json','async':True,'background':True}
def run_background_task(task,client_ip):
    gid=str(task['generationId']);mode=str(task.get('mode') or 'analyze');model=str(task.get('model') or 'gpt-image-2');aspect=str(task.get('aspect') or '1:1');images=task.get('images') or [];user=str(task.get('userPrompt') or '')
    failure_stage='analysis'
    try:
        if mode=='analyze':
            status,data=internal_post('/api/analyze',task,timeout=900)
            if status>=400: raise RuntimeError(data.get('error') if isinstance(data,dict) else f'HTTP {status}')
            prompts=data.get('prompts') or []
            history_update_meta(gid,analysisStatus='success',analysisSucceededAt=time.strftime('%Y-%m-%dT%H:%M:%S'),failureStage='')
        elif mode=='resume':
            prompts=task.get('prompts') or []
            if not prompts: raise RuntimeError('待恢复任务没有可用提示词')
            history_update_meta(gid,analysisStatus='success',analysisSucceededAt=time.strftime('%Y-%m-%dT%H:%M:%S'),failureStage='')
        else:
            count=max(1,min(6,int(task.get('count') or 1)));title=(user[:24]+'…') if len(user)>24 else (user or '详情图');prompts=[{'title':title,'purpose':'按提示词','prompt':user} for _ in range(count)]
            history_merge({'id':gid,'generationId':gid,'createdAt':time.strftime('%Y-%m-%dT%H:%M:%S'),'ip':client_ip,'model':model,'aspect':aspect,'userPrompt':user,'prompts':prompts,'images':images,'results':[{'status':'queued','url':''} for _ in prompts],'status':'generating'})
        if not prompts: raise RuntimeError('分析未返回提示词')
        failure_stage='image_submit'
        history_update_state(gid,'generating')
        history_update_meta(gid,imageSubmitStatus='started',imageSubmitStartedAt=time.strftime('%Y-%m-%dT%H:%M:%S'))
        workers=[]
        def create_one(index,item):
            try:
                history_update_result(gid,index,{'status':'creating','url':''})
                payload=image_request_body(model,str(item.get('prompt') or ''),images,aspect);payload.update({'index':index,'generationId':gid,'model':model,'userPrompt':user,'aspect':aspect,'title':str(item.get('title') or '')})
                status,result=internal_post('/api/create',payload)
                if status>=400:
                    history_update_result(gid,index,{'status':'error','url':'','error':str(result.get('error') if isinstance(result,dict) else result),'rawError':result});return
                task_id=str(result.get('taskId') or result.get('id') or '') if isinstance(result,dict) else ''
                if not task_id or (isinstance(result,dict) and result.get('url')): return
                history_update_result(gid,index,{'status':'polling','url':'','taskId':task_id})
                deadline=time.time()+150
                while time.time()<deadline:
                    time.sleep(5);query_status,query=internal_post('/api/query',{'taskId':task_id,'model':model,'generationId':gid,'index':index})
                    if query_status>=400:
                        history_update_result(gid,index,{'status':'error','url':'','taskId':task_id,'error':str(query.get('error') if isinstance(query,dict) else query),'rawError':query});return
                    if isinstance(query,dict) and query.get('url'): return
                    if isinstance(query,dict) and str(query.get('status') or '').lower() in ('failed','failure','error'):
                        history_update_result(gid,index,{'status':'error','url':'','taskId':task_id,'error':str(query.get('error') or query.get('status')),'rawError':query});return
                history_update_result(gid,index,{'status':'error','url':'','taskId':task_id,'error':'等待 150 秒仍未返回结果'})
            except Exception as error:
                history_update_result(gid,index,{'status':'error','url':'','error':f'本地生图提交异常：{error}'})
        prior_results=task.get('results') if isinstance(task.get('results'),list) else []
        for index,item in enumerate(prompts,1):
            if mode=='resume' and index<=len(prior_results) and isinstance(prior_results[index-1],dict) and prior_results[index-1].get('url'): continue
            worker=threading.Thread(target=create_one,args=(index,item),daemon=True);worker.start();workers.append(worker)
        for worker in workers:worker.join()
        snapshot=next((r for r in history_records() if str(r.get('generationId'))==gid),{})
        results=snapshot.get('results') or [];ok=sum(1 for item in results if item.get('url'))
        final_status='completed' if ok==len(prompts) else ('partial' if ok else 'failed')
        history_update_state(gid,final_status,'',failure_stage if final_status!='completed' else '')
        history_update_meta(gid,imageSubmitStatus='completed' if final_status=='completed' else 'failed')
    except Exception as error:
        print(f'[task] {gid} failed during {failure_stage}: {error}',flush=True);history_update_state(gid,'failed',str(error),failure_stage)
def run_analysis_batch(batch_id,images,user_prompt,model,upstream):
    with ANALYSIS_BATCH_LOCK: batch=ANALYSIS_BATCHES.get(batch_id)
    if not batch:return
    for index,image in enumerate(images,1):
        started=time.time()
        payload={'images':[image],'userPrompt':user_prompt,'count':6,'model':'gpt-image-2','aspect':'1:1','analyzeModel':model,'analysisUpstream':upstream,'analysisOnly':True}
        try:
            status,data=internal_post('/api/analyze',payload,timeout=900)
            prompts=data.get('prompts') if isinstance(data,dict) else []
            result={'case':index,'httpStatus':status,'elapsedSec':round(time.time()-started,2),'promptCount':len(prompts or []),'ok':status<400 and len(prompts or [])==6}
            if not result['ok']: result['error']=str(data.get('error') if isinstance(data,dict) else data)[:500]
        except Exception as error:
            result={'case':index,'elapsedSec':round(time.time()-started,2),'promptCount':0,'ok':False,'error':str(error)[:500]}
        with ANALYSIS_BATCH_LOCK:
            batch=ANALYSIS_BATCHES.get(batch_id)
            if not batch:return
            batch['results'].append(result);batch['updatedAt']=time.strftime('%Y-%m-%dT%H:%M:%S')
    with ANALYSIS_BATCH_LOCK:
        if batch_id in ANALYSIS_BATCHES: ANALYSIS_BATCHES[batch_id]['status']='completed';ANALYSIS_BATCHES[batch_id]['updatedAt']=time.strftime('%Y-%m-%dT%H:%M:%S')
def mirror_upload(path):
    if not (REMOTE_UPLOAD_HOST and REMOTE_UPLOAD_DIR): return
    import subprocess
    cmd=['scp','-o','BatchMode=yes','-o','ConnectTimeout=8']
    if REMOTE_UPLOAD_KEY: cmd += ['-i',REMOTE_UPLOAD_KEY]
    subprocess.run(cmd+[str(path),f'{REMOTE_UPLOAD_USER}@{REMOTE_UPLOAD_HOST}:{REMOTE_UPLOAD_DIR}/{path.name}'],check=True,timeout=30)
def public_upload_config():
    config={}
    try:
        config=json.loads(PUBLIC_UPLOAD_CONFIG.read_text('utf-8'))
    except FileNotFoundError:
        pass
    except Exception as error:
        raise RuntimeError(f'公网图片上传配置无效：{error}')
    return (
        str(PUBLIC_UPLOAD_API_BASE or config.get('apiBaseUrl') or '').rstrip('/'),
        str(PUBLIC_UPLOAD_TOKEN or config.get('uploadToken') or '').strip(),
    )
def image_upstream_config(store):
    config={}
    try: config=json.loads(IMAGE_UPSTREAM_CONFIG.read_text('utf-8'))
    except FileNotFoundError: pass
    except Exception as error: raise RuntimeError(f'生图上游配置无效：{error}')
    active=str(os.environ.get('IMAGE_GENERATION_UPSTREAM') or config.get('active') or 'hfsy').strip().lower()
    if active not in IMAGE_UPSTREAMS: raise RuntimeError('不支持的生图上游')
    key=str(store.get(f'image_{active}') or (store.get('analysis_tyai') if active=='tyai' else store.get('hfsy')) or '').strip()
    valid_key(key)
    return active,IMAGE_UPSTREAMS[active],key
def upstream_image_url(url):
    """Use a hostname-based public download URL for the configured upload service."""
    text=str(url or '')
    try:
        api_base,_=public_upload_config()
    except Exception:
        return text
    if api_base and text.startswith(f'{api_base}/files/'):
        return 'https://images.weserv.nl/?url='+urllib.parse.quote(text,safe='')
    return text
def switch_image_proxy(body):
    """Alternate two public image-proxy hostnames after a gateway-side fetch outage."""
    def switch(url):
        text=str(url or '')
        if text.startswith('https://images.weserv.nl/?url='): return text.replace('https://images.weserv.nl/?url=','https://wsrv.nl/?url=',1)
        if text.startswith('https://wsrv.nl/?url='): return text.replace('https://wsrv.nl/?url=','https://images.weserv.nl/?url=',1)
        return text
    if isinstance(body.get('reference_images'),list): body['reference_images']=[switch(url) for url in body['reference_images']]
    for content in body.get('contents',[]) if isinstance(body.get('contents'),list) else []:
        for part in content.get('parts',[]) if isinstance(content,dict) else []:
            file_data=part.get('fileData') if isinstance(part,dict) else None
            if isinstance(file_data,dict) and file_data.get('fileUri'): file_data['fileUri']=switch(file_data['fileUri'])
    return body
def warm_upstream_image(url):
    """Fill the image proxy cache before a gateway with a short download timeout fetches it."""
    target=str(url or '')
    if not target.startswith(('https://images.weserv.nl/?url=','https://wsrv.nl/?url=')): return
    now=time.time()
    with IMAGE_WARM_LOCK:
        if now-WARMED_IMAGE_URLS.get(target,0)<1800: return
        if now-IMAGE_WARM_FAILURES.get(target,0)<60: return
        ready=WARMING_IMAGE_URLS.get(target)
        if ready is None:
            ready=threading.Event();WARMING_IMAGE_URLS[target]=ready;owner=True
        else: owner=False
    if not owner:
        ready.wait(100)
        with IMAGE_WARM_LOCK:
            if time.time()-WARMED_IMAGE_URLS.get(target,0)<1800: return
        return warm_upstream_image(url)
    request=urllib.request.Request(target,headers={'User-Agent':'WatchStudio/1.0','Accept':'image/*'})
    try:
        with direct_open(request,timeout=90) as response:
            if response.status!=200: raise RuntimeError(f'HTTP {response.status}')
            total=0
            while chunk:=response.read(1024*1024):
                total+=len(chunk)
                if total>MAX_UPLOAD: raise RuntimeError('图片超过预热大小限制')
        with IMAGE_WARM_LOCK:
            WARMED_IMAGE_URLS[target]=time.time()
            IMAGE_WARM_FAILURES.pop(target,None)
    except Exception as error:
        with IMAGE_WARM_LOCK: IMAGE_WARM_FAILURES[target]=time.time()
        raise RuntimeError(f'参考图公网预热失败：{error}')
    finally:
        with IMAGE_WARM_LOCK:
            WARMING_IMAGE_URLS.pop(target,None);ready.set()
def warm_request_images(body):
    urls=[]
    if isinstance(body.get('reference_images'),list): urls.extend(body['reference_images'])
    for content in body.get('contents',[]) if isinstance(body.get('contents'),list) else []:
        for part in content.get('parts',[]) if isinstance(content,dict) else []:
            file_data=part.get('fileData') if isinstance(part,dict) else None
            if isinstance(file_data,dict): urls.append(file_data.get('fileUri'))
    for url in dict.fromkeys(str(url or '') for url in urls):
        try:
            warm_upstream_image(url)
        except Exception as error:
            # Warming the public proxy cache is only an optimization. A cache
            # gateway timeout must not prevent the image request from reaching
            # the configured generation upstream.
            print(f'reference image prewarm failed; continuing with generation request: {error}',flush=True)
def analysis_image_source(image):
    """Analysis accepts data URLs, avoiding fragile third-party URL downloads."""
    source=local_image_data(image)
    if source.startswith('data:'): return source
    cache_path=REFERENCE_CACHE/(hashlib.sha256(source.encode()).hexdigest()+'.bin')
    if cache_path.exists():
        mime=mimetypes.guess_type(str(image))[0] or 'image/jpeg'
        return f'data:{mime};base64,'+base64.b64encode(cache_path.read_bytes()).decode()
    try:
        api_base,_=public_upload_config()
    except Exception:
        api_base=''
    if not (api_base and source.startswith(f'{api_base}/files/')):
        return source
    targets=[source];fallback=upstream_image_url(source)
    if fallback!=source: targets.append(fallback)
    errors=[]
    for target in targets:
        for attempt in range(3):
            request=urllib.request.Request(target,headers={'User-Agent':'WatchStudio/1.0','Accept':'image/*'})
            try:
                with direct_open(request,timeout=90) as response:
                    data=response.read(15*1024*1024+1);mime=(response.headers.get_content_type() or 'image/jpeg')
                if not data or len(data)>15*1024*1024: raise RuntimeError('图片为空或超过 15 MB')
                REFERENCE_CACHE.mkdir(parents=True,exist_ok=True);cache_path.write_bytes(data)
                return f'data:{mime};base64,'+base64.b64encode(data).decode()
            except Exception as error:
                errors.append(str(error));time.sleep(1+attempt)
    raise RuntimeError('无法读取参考图用于分析：'+' | '.join(errors[-2:]))
def upload_to_public_server(path,content_type):
    api_base,upload_token=public_upload_config()
    if not (api_base and upload_token):
        raise RuntimeError('未配置公网图片上传服务')
    mime=content_type or mimetypes.guess_type(path.name)[0] or 'image/jpeg'
    payload={'name':path.name,'mime':mime,'dataBase64':base64.b64encode(path.read_bytes()).decode()}
    request=urllib.request.Request(
        f'{api_base}/v1/files',data=json.dumps(payload).encode(),method='POST',
        headers={'Content-Type':'application/json','Accept':'application/json','X-Upload-Token':upload_token,'User-Agent':'WatchStudio/1.0'},
    )
    try:
        with direct_open(request,timeout=90) as response:
            result=json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as error:
        detail=error.read().decode('utf-8','replace')[:500]
        raise RuntimeError(f'公网图片上传失败（HTTP {error.code}）：{detail}')
    except Exception as error:
        raise RuntimeError(f'公网图片上传失败：{error}')
    url=str((result.get('file') or {}).get('url') or '') if isinstance(result,dict) else ''
    if not url.startswith(('http://','https://')): raise RuntimeError('公网图片上传服务未返回有效链接')
    return url
def generation_folder(ip,generation_id):
    safe_ip=re.sub(r'[^A-Za-z0-9_.-]+','_',str(ip or 'unknown'))
    folder=OUTPUTS/safe_ip/str(generation_id or 'untitled')
    folder.mkdir(parents=True,exist_ok=True)
    return folder
def save_generated_image(source_url,ip,generation_id,index):
    source=str(source_url or '')
    if not source:return ('','')
    try:
        if source.startswith('data:'):
            _,encoded=source.split(',',1);data=base64.b64decode(encoded)
        else:
            req=urllib.request.Request(source,headers={'User-Agent':'WatchStudio/1.0'})
            with direct_open(req,timeout=90) as response:data=response.read(30*1024*1024+1)
        if len(data)>30*1024*1024: raise ValueError('生成图片超过 30 MB')
        folder=generation_folder(ip,generation_id);path=folder/f'{int(index or 0):02d}.png';previous_url=''
        if path.exists():
            snapshot=folder/f'{int(index or 0):02d}-v{time.time_ns()}.png'
            shutil.copyfile(path,snapshot)
            previous_url=f'/outputs/{urllib.parse.quote(snapshot.relative_to(OUTPUTS).as_posix())}'
        path.write_bytes(data)
        return f'/outputs/{urllib.parse.quote(path.relative_to(OUTPUTS).as_posix())}',previous_url
    except Exception as exc:
        print(f'failed to save generated image: {exc}',flush=True)
        return ('','')
def records():
    return history_records()
class Handler(BaseHTTPRequestHandler):
    def _session_ok(self):
        if not AUTH_ENABLED:return True
        match=re.search(r'(?:^|;\s*)watchstudio_session=([a-f0-9]{64})(?:;|$)',self.headers.get('Cookie',''))
        if not match:return False
        token=match.group(1);now=time.time()
        with LOGIN_LOCK:
            expires=LOGIN_SESSIONS.get(token)
            if not expires:return False
            if expires<now:
                LOGIN_SESSIONS.pop(token,None);return False
            return True
    def _send_login(self,status=200,error=False):
        data=render_login(error);self.send_response(status);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(data)
    def _handle_login(self):
        try:
            length=min(int(self.headers.get('Content-Length','0')),4096)
            form=urllib.parse.parse_qs(self.rfile.read(length).decode('utf-8','replace'))
            username=(form.get('username') or [''])[0][:128];password=(form.get('password') or [''])[0][:1024]
            client=str(self.headers.get('X-Remote-Addr') or self.client_address[0]);now=time.time();config=json.loads(LOGIN_CONFIG.read_text())
            with LOGIN_LOCK:
                attempts=[t for t in LOGIN_ATTEMPTS.get(client,[]) if now-t<600]
                LOGIN_ATTEMPTS[client]=attempts
                blocked=len(attempts)>=8
            valid=False
            if not blocked and username==str(config.get('username') or ''):
                digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(config['salt']),int(config.get('rounds',310000))).hex()
                valid=hmac.compare_digest(digest,str(config.get('passwordHash') or ''))
            if not valid:
                with LOGIN_LOCK:LOGIN_ATTEMPTS.setdefault(client,[]).append(now)
                return self._send_login(429 if blocked else 401,True)
            with LOGIN_LOCK:LOGIN_ATTEMPTS.pop(client,None)
            token=secrets.token_hex(32)
            with LOGIN_LOCK:LOGIN_SESSIONS[token]=now+LOGIN_TTL
            self.send_response(303);self.send_header('Location','/studio/');self.send_header('Set-Cookie',f'watchstudio_session={token}; Path=/studio/; Max-Age={LOGIN_TTL}; HttpOnly; Secure; SameSite=Lax');self.send_header('Cache-Control','no-store');self.end_headers()
        except Exception:
            return self._send_login(503,True)
    def _handle_logout(self):
        match=re.search(r'(?:^|;\s*)watchstudio_session=([a-f0-9]{64})(?:;|$)',self.headers.get('Cookie',''))
        if match:
            with LOGIN_LOCK:LOGIN_SESSIONS.pop(match.group(1),None)
        self.send_response(303);self.send_header('Location','/studio/');self.send_header('Set-Cookie','watchstudio_session=; Path=/studio/; Max-Age=0; HttpOnly; Secure; SameSite=Lax');self.send_header('Cache-Control','no-store');self.end_headers()
    def do_GET(self):
        route=urllib.parse.urlsplit(self.path).path
        if route=='/login' and AUTH_ENABLED:return self._send_login()
        if not self._session_ok():
            if route in ('/','/index.html'):return self._send_login()
            return json_response(self,401,{'error':'login required'})
        if self.path.startswith('/api/test-analysis-batch/'):
            batch_id=urllib.parse.unquote(self.path.rsplit('/',1)[-1])
            with ANALYSIS_BATCH_LOCK: batch=ANALYSIS_BATCHES.get(batch_id)
            return json_response(self,200,batch) if batch else json_response(self,404,{'error':'test batch not found'})
        if self.path in ('/','/index.html'):
            data=HTML.encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store, no-cache, must-revalidate, max-age=0');self.send_header('Pragma','no-cache');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
        if self.path=='/api/keys':
            store=key_store();return json_response(self,200,{'hfsy':store.get('hfsy','')} if store.get('hfsy') else {})
        if self.path=='/api/prompt-favorites':return json_response(self,200,{'favorites':prompt_favorites()})
        if self.path=='/api/history':return json_response(self,200,{'records':records()})
        if self.path.startswith('/api/reference-image?'):
            query=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);source=(query.get('url') or [''])[0]
            if not source.startswith(('http://','https://')):return json_response(self,400,{'error':'invalid reference image URL'})
            cache_path=REFERENCE_CACHE/(hashlib.sha256(source.encode()).hexdigest()+'.bin')
            if not cache_path.exists():
                self.send_response(302);self.send_header('Location',source);self.send_header('Cache-Control','no-store');self.end_headers();return
            use_thumb=(query.get('thumb') or [''])[0]=='1';path=cache_path
            if use_thumb:
                thumb_path=cache_path.with_name(cache_path.name+'.thumb.jpg')
                if not thumb_path.exists():
                    with REFERENCE_THUMB_LOCK:
                        if not thumb_path.exists():
                            try:
                                subprocess.run(['/usr/bin/sips','-Z','640','-s','format','jpeg','-s','formatOptions','78',str(cache_path),'--out',str(thumb_path)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20,check=True)
                            except Exception:pass
                if thumb_path.exists():path=thumb_path
            data=path.read_bytes();mime='image/jpeg' if use_thumb and path!=cache_path else mimetypes.guess_type(urllib.parse.urlsplit(source).path)[0]
            if not mime:mime='image/jpeg'
            self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','public, max-age=86400');self.end_headers();self.wfile.write(data);return
        if self.path.startswith('/uploads/'):
            name=self.path.split('/uploads/',1)[1].split('?',1)[0]
            path=(UPLOADS/name).resolve()
            if path.parent != UPLOADS.resolve() or not path.exists(): return json_response(self,404,{'error':'upload not found'})
            data=path.read_bytes();self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(path.name)[0] or 'image/jpeg');self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','public, max-age=86400');self.end_headers();self.wfile.write(data);return
        if self.path.startswith('/outputs/'):
            name=urllib.parse.unquote(self.path.split('/outputs/',1)[1].split('?',1)[0]);path=(OUTPUTS/name).resolve()
            if OUTPUTS.resolve() not in path.parents or not path.exists(): return json_response(self,404,{'error':'output not found'})
            data=path.read_bytes();self.send_response(200);self.send_header('Content-Type','image/png');self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store, no-cache, must-revalidate, max-age=0');self.send_header('Pragma','no-cache');self.end_headers();self.wfile.write(data);return
        json_response(self,404,{'error':'not found'})
    def do_POST(self):
        route=urllib.parse.urlsplit(self.path).path
        if route=='/login' and AUTH_ENABLED:return self._handle_login()
        if route=='/logout' and AUTH_ENABLED:return self._handle_logout()
        if not self._session_ok():return json_response(self,401,{'error':'login required'})
        try:body=read_json(self)
        except Exception:return json_response(self,400,{'error':'invalid json'})
        try:
            if self.path=='/api/tasks':
                images=body.get('images') or []
                if not images: raise ValueError('请先上传至少 1 张参考图')
                mode=str(body.get('mode') or 'analyze')
                if mode not in ('analyze','prompt'): raise ValueError('不支持的生成方式')
                if mode=='prompt' and not str(body.get('userPrompt') or '').strip(): raise ValueError('请输入总体要求/提示词')
                count=max(1,min(6,int(body.get('count') or 6)));gid=f"task-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
                task={**body,'generationId':gid,'count':count,'mode':mode}
                history_merge({'id':gid,'generationId':gid,'createdAt':time.strftime('%Y-%m-%dT%H:%M:%S'),'ip':str(self.client_address[0]),'model':str(body.get('model') or 'gpt-image-2'),'aspect':str(body.get('aspect') or '1:1'),'userPrompt':str(body.get('userPrompt') or ''),'images':images,'prompts':[],'results':[{'status':'queued','url':''} for _ in range(count)],'status':'analyzing' if mode=='analyze' else 'queued'})
                threading.Thread(target=run_background_task,args=(task,str(self.client_address[0])),daemon=True).start()
                return json_response(self,202,{'ok':True,'generationId':gid,'status':'analyzing' if mode=='analyze' else 'queued'})
            if self.path=='/api/tasks/resume':
                gid=str(body.get('generationId') or '').strip()
                record=next((item for item in history_records() if str(item.get('generationId') or '')==gid),None)
                if not record: raise ValueError('未找到需要恢复的任务')
                prompts=record.get('prompts') if isinstance(record.get('prompts'),list) else []
                if not prompts: raise ValueError('该任务尚未生成可恢复的提示词')
                active={'analyzing','queued','creating','retrying','generating','polling'}
                if any(str(item.get('status') or '') in active and item.get('taskId') for item in record.get('results') or []): raise ValueError('该任务已有正在执行的生图请求，无需恢复')
                task={**record,'generationId':gid,'prompts':prompts,'mode':'resume','count':len(prompts)}
                history_update_state(gid,'generating')
                threading.Thread(target=run_background_task,args=(task,str(self.client_address[0])),daemon=True).start()
                return json_response(self,202,{'ok':True,'generationId':gid,'status':'generating'})
            if self.path=='/api/keys':
                val=str(body.get('hfsy') or '').strip();store=key_store()
                if val:valid_key(val);store['hfsy']=val
                else:store.pop('hfsy',None)
                DATA.mkdir(exist_ok=True);KEYS.write_text(json.dumps(store,ensure_ascii=False,indent=2));KEYS.chmod(0o600);return json_response(self,200,{'hfsy':store.get('hfsy','')} if store.get('hfsy') else {})
            if self.path=='/api/analysis-key':
                upstream=str(body.get('upstream') or 'owlai').strip().lower()
                if upstream not in ANALYSIS_UPSTREAMS: raise ValueError('不支持的分析上游')
                val=str(body.get('analysis') or '').strip();valid_key(val);store=key_store();store[f'analysis_{upstream}']=val
                DATA.mkdir(exist_ok=True);KEYS.write_text(json.dumps(store,ensure_ascii=False,indent=2));KEYS.chmod(0o600);return json_response(self,200,{'ok':True})
            if self.path=='/api/test-analysis':
                upstream=str(body.get('upstream') or 'owlai').strip().lower()
                if upstream not in ANALYSIS_UPSTREAMS: raise ValueError('不支持的分析上游')
                store=key_store();analysis_key=str(store.get(f'analysis_{upstream}') or store.get('analysis') or '').strip();valid_key(analysis_key)
                started=time.time()
                images=body.get('images') if isinstance(body.get('images'),list) else []
                if images:
                    content=[{'type':'text','text':'Vision-analysis connectivity test. Inspect the supplied reference image and the user context below. Reply with exactly OK.\nUser context:\n'+str(body.get('userPrompt') or '')[:6000]}]
                    for image in images[:3]: content.append({'type':'image_url','image_url':{'url':analysis_image_source(image)}})
                else: content='Reply with OK only.'
                status,payload=proxy('/v1/chat/completions',analysis_key,{'model':str(body.get('model') or 'gpt-5.6-terra'),'messages':[{'role':'user','content':content}],'temperature':0,'max_tokens':8,'stream':False},retries=0,timeout=90,base=ANALYSIS_UPSTREAMS[upstream])
                content=''
                if isinstance(payload,dict): content=str(payload.get('choices',[{}])[0].get('message',{}).get('content','') or '')
                ok=status<400 and bool(content.strip())
                return json_response(self,200 if ok else status,{'ok':ok,'status':status,'model':'gpt-5.6-terra','latencyMs':round((time.time()-started)*1000),'reply':content.strip() if ok else '','error':payload.get('error') if isinstance(payload,dict) else payload})
            if self.path=='/api/test-analysis-batch':
                upstream=str(body.get('upstream') or 'owlai').strip().lower()
                if upstream not in ANALYSIS_UPSTREAMS: raise ValueError('不支持的分析上游')
                source=next((record for record in history_records() if str(record.get('userPrompt') or '').strip()),None)
                if not source: raise ValueError('没有可用于测试的历史总体要求')
                images=[];seen=set()
                for record in history_records():
                    for image in record.get('images') or []:
                        image=str(image or '')
                        if image and image not in seen:
                            seen.add(image);images.append(image)
                        if len(images)>=5: break
                    if len(images)>=5: break
                if len(images)<5: raise ValueError('可用的不同参考图不足 5 张')
                batch_id='analysis-batch-'+uuid.uuid4().hex[:10]
                batch={'id':batch_id,'status':'running','upstream':upstream,'model':str(body.get('model') or 'gpt-5.6-sol'),'sourceGenerationId':source.get('generationId'),'cases':len(images),'results':[],'createdAt':time.strftime('%Y-%m-%dT%H:%M:%S'),'updatedAt':time.strftime('%Y-%m-%dT%H:%M:%S')}
                with ANALYSIS_BATCH_LOCK: ANALYSIS_BATCHES[batch_id]=batch
                threading.Thread(target=run_analysis_batch,args=(batch_id,images,str(source.get('userPrompt') or ''),batch['model'],upstream),daemon=True).start()
                return json_response(self,202,{'ok':True,'batchId':batch_id,'cases':len(images),'upstream':upstream,'sourceGenerationId':source.get('generationId')})
            if self.path=='/api/history':history_merge(body.get('record') or {});return json_response(self,200,{'ok':True})
            if self.path=='/api/prompt-favorites':
                action=str(body.get('action') or 'save')
                with FILE_LOCK:
                    values=prompt_favorites()
                    if action in ('save','upsert'):
                        prompt=str(body.get('prompt') or '').strip()
                        if not prompt: raise ValueError('请输入要收藏的提示词')
                        if len(prompt)>20000: raise ValueError('提示词不能超过 20000 个字符')
                        favorite_id=str(body.get('id') or '').strip()
                        existing=next((item for item in values if str(item.get('id') or '')==favorite_id),None) if favorite_id else next((item for item in values if str(item.get('prompt') or '')==prompt),None)
                        title=str(body.get('title') or '').strip() or re.sub(r'\s+',' ',prompt)[:36]
                        if existing:
                            existing.update({'title':title[:80],'prompt':prompt,'updatedAt':time.strftime('%Y-%m-%dT%H:%M:%S')})
                        else:
                            values.insert(0,{'id':'fav-'+uuid.uuid4().hex[:12],'title':title[:80],'prompt':prompt,'createdAt':time.strftime('%Y-%m-%dT%H:%M:%S')})
                            values=values[:200]
                    elif action=='delete':
                        favorite_id=str(body.get('id') or '')
                        values=[item for item in values if str(item.get('id') or '')!=favorite_id]
                    else: raise ValueError('不支持的收藏操作')
                    write_prompt_favorites(values)
                return json_response(self,200,{'ok':True,'favorites':values})
            if self.path=='/api/history/cleanup':
                scope=str(body.get('scope') or '')
                if scope not in ('failed_without_images','all_failed'): raise ValueError('不支持的清理范围')
                removed=history_remove_failed(scope)
                return json_response(self,200,{'ok':True,'removed':len(removed),'generationIds':[str(item.get('generationId') or '') for item in removed]})
            if self.path=='/api/upload':
                raw=str(body.get('dataUrl') or '');head,encoded=raw.split(',',1);data=base64.b64decode(encoded); 
                if len(data)>MAX_UPLOAD:raise ValueError('图片过大')
                UPLOADS.mkdir(parents=True,exist_ok=True);ext=mimetypes.guess_extension(str(body.get('contentType') or 'image/jpeg')) or '.jpg';name=f'{int(time.time())}-{uuid.uuid4().hex}{ext}';(UPLOADS/name).write_bytes(data)
                public_url=upload_to_public_server(UPLOADS/name,str(body.get('contentType') or 'image/jpeg'))
                REFERENCE_CACHE.mkdir(parents=True,exist_ok=True)
                (REFERENCE_CACHE/(hashlib.sha256(public_url.encode()).hexdigest()+'.bin')).write_bytes(data)
                return json_response(self,200,{'url':public_url,'serverPath':str(UPLOADS/name),'via':'public-upload-server'})
            if self.path=='/api/fetch-image':
                url=str(body.get('url') or '');req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'});data=direct_open(req,timeout=60).read(25*1024*1024+1)
                self.send_response(200);self.send_header('Content-Type','image/png');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
            if self.path in ('/api/analyze','/api/create','/api/query'):
                store=key_store()
                is_analysis=self.path=='/api/analyze'
                if is_analysis:
                    requested_model=str(body.get('analyzeModel') or '')
                    body['analyzeModel']=requested_model if requested_model in ('gpt-5.6-terra','gpt-5.6-sol') else 'gpt-5.6-sol'
                    analysis_upstream='owlai+tyai'
                    key='';analysis_base=''
                else:
                    image_upstream,image_base,key=image_upstream_config(store)
                    key=str(body.pop('apiKey', '') or key).strip();valid_key(key)
                if self.path=='/api/analyze':
                    images=body.get('images') or [];count=max(1,min(6,int(body.get('count') or 6)));user=str(body.get('userPrompt') or '')
                    print(f"[analyze] 收到 ip={self.client_address[0]} upstream={analysis_upstream} model={body.get('analyzeModel')} count={count}, 等待分析锁...",flush=True)
                    if not ANALYZE_SEM.acquire(timeout=420):
                        print('analyze queue timeout, dropped',flush=True)
                        return json_response(self,503,{'error':'上游分析通道繁忙,排队超过 7 分钟未轮上,请稍后重试'})
                    print(f"[analyze] 获得锁, ip={self.client_address[0]} 开始调用上游",flush=True)
                    try:
                        creative_seed=uuid.uuid4().hex[:10]
                        no_overlay_text=requests_no_overlay_text(user)
                        text_policy=('The user explicitly requests no graphic text. Do not add headlines, captions, callouts, labels, logos, watermarks, typography, or any other overlay lettering to any image. Set on_image_copy to an empty string. Preserve only authentic text and markings physically present on the product in the reference image.' if no_overlay_text else 'Every image MUST contain purposeful, visible English ecommerce typography. The on_image_copy field must be a non-empty single string in this format: "HEADLINE | SHORT SUPPORTING LINE"; for a feature-education image it may add "| CALLOUT 1 • CALLOUT 2". Use concise, credible English that refers only to visibly supported design traits; do not invent materials, measurements, certifications, ratings or performance promises. The prompt MUST reproduce the exact copy in quotation marks and explicitly instruct the image model to render all of those exact English words, with a concrete placement, hierarchy, contrast and whitespace treatment. Use a restrained luxury-campaign headline rather than filling every image with text. Avoid placeholder copy, vague instructions such as "add supplied text", Chinese, random brand logos, or unreadable text. Text should feel editorial and premium, not like a technical spec sheet.')
                        prompt_schema_text=('Each prompt must be a self-contained 110-190 word English image-generation prompt that preserves exact product identity and the planned distinct composition. Do not request any overlay typography; set on_image_copy to an empty string. Explicitly say no headline, caption, callout, logo, watermark, or other added text, while preserving authentic product markings.' if no_overlay_text else 'Every prompt must be a self-contained 110-190 word English image-generation prompt. It must state the exact product identity lock, the shared art direction, the distinct scene/composition, and the exact English on-image copy to visibly render.')
                        prompt_field_schema=('non-empty title, purpose, camera_angle, scene and prompt, plus an empty on_image_copy string' if no_overlay_text else 'non-empty title, purpose, camera_angle, scene, on_image_copy and prompt')
                        prompt=f'''You are a senior Amazon luxury-watch art director and conversion-copy strategist. Create a premium, purchase-motivating product-detail image plan, not a set of near-identical catalogue photos.

INSTRUCTION PRIORITY — HIGHEST PRIORITY
The user's request is the highest-priority creative instruction. If any default rule, art direction, scene suggestion, copywriting requirement, typography policy, composition, or generated prompt below conflicts with the user's request, follow the user's request and disregard the conflicting lower-priority instruction. Never reinterpret a clear user constraint as optional.

REFERENCE RULES
- Image 1 is the sole product identity source. Preserve its watch exactly: case silhouette, dial layout, existing logo and English dial text, markers, hands, subdials, date window, crown, buttons, bracelet/strap, colour, proportions, finish and realistic crystal reflections. Never invent or remove product details, specifications, claims, a second watch, or a back view.
- Images 2+ are only supplementary detail/style references. When there is any conflict, image 1 wins.
- Build a fresh, product-led art direction for this run from the actual watch and the user's request. Keep only a light family resemblance across the set (compatible palette, typography and lighting logic), while making each image feel like a genuinely different chapter rather than the same studio shoot with a new crop. Never import a default visual template.

ART DIRECTION SOURCE
Derive every visual decision exclusively from the uploaded reference images and the user's request. First analyse the actual watch: case shape, dial architecture, visible materials, dominant and accent colours, form language, customer positioning and strongest visible selling point. Let those findings determine the palette, background, props, lighting, typography, mood, composition and scenario. Do not append, import or default to any preset campaign style, colour scheme, surface, prop, lighting setup, lifestyle setting or brand atmosphere that is not supported by the analysis or the user's request. Supplementary images may influence style only when the user supplied them; image 1 always remains the product identity source.

CONVERSION AND LAYOUT RULES
Each image must earn a different place in an Amazon detail page. It needs a distinct customer question, camera distance, product placement, scene/surface and text layout. For N=6, select and cover six distinct sales jobs from this library: product identity, signature dial/design story, tactile craftsmanship/detail proof, believable on-wrist scale, text-forward benefit education using only visible traits, premium occasion/gifting decision, styling context, and an unexpected product-led editorial moment. Choose a fresh, non-template order for every analysis run. NEVER reserve image 1 for a hero image: it may be a macro, on-wrist scene, text-led editorial, or any other strongest opening selected for this particular product and request. If the user requests randomness or variation, deliberately shuffle the narrative order and choose a new, defensible visual direction; do not fall back to a predictable hero-first sequence. For fewer images choose the highest-value jobs; for more than one include at least one close macro, one on-wrist composition, and one text-forward editorial layout. Use at least three clearly different scene/surface categories in a six-image set, and allow at most one isolated studio product shot.

{text_policy}

Output requirements (strict):
1) selling_points_cn: concise Chinese array based only on visible reference details.
2) identity_lock_en: an English identity-lock prompt.
3) prompts: exactly {count} objects total, each with {prompt_field_schema}. Do not output alternatives, variants, optional extras, duplicate plans, or any object beyond {count}. {prompt_schema_text} No duplicate scene, angle, sales job or text hierarchy.

Only output a valid JSON object with exactly these top-level keys.
Creative variation token for this planning run: {creative_seed}. Use it as an instruction to make a fresh, non-default choice of opening image, sales-job order, scene progression and visual direction; never mention this token in the output.
User request (highest priority; obey every explicit constraint): {user}'''
                        analysis_content=[{'type':'text','text':prompt}]
                        for idx,image in enumerate(images):
                            label='PRODUCT IDENTITY SOURCE — this is the watch that must be reproduced exactly.' if idx==0 else f'SUPPLEMENTARY REFERENCE {idx} — use only for compatible detail, scene, lighting or styling inspiration; never override product identity.'
                            image_url=analysis_image_source(image)
                            analysis_content.extend([{'type':'text','text':label},{'type':'image_url','image_url':{'url':image_url}}])
                        analysis_request={'model':str(body.get('analyzeModel') or 'gpt-5.6-sol'),'messages':[{'role':'system','content':'Return compact valid JSON only. Be a demanding ecommerce art director: reject generic repeated product photography and ensure every requested text element is concrete and renderable.'},{'role':'user','content':analysis_content}],'temperature':.7,'max_tokens':12000,'stream':False,'response_format':{'type':'json_object'}}
                        data,normalized,used_analysis_upstream=run_parallel_analysis(analysis_request,count,store,str(self.client_address[0]),no_overlay_text)
                        data['prompts']=normalized;data['analysisUpstreamUsed']=used_analysis_upstream
                        data['generationId']=str(body.get('generationId') or f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}");data['outputFolder']=str(generation_folder(self.client_address[0],data['generationId']))
                        if not body.get('analysisOnly'): history_merge({'id':data['generationId'],'createdAt':time.strftime('%Y-%m-%dT%H:%M:%S'),'generationId':data['generationId'],'ip':str(self.client_address[0]),'model':str(body.get('model') or 'gpt-image-2'),'aspect':str(body.get('aspect') or '1:1'),'userPrompt':user,'selling_points_cn':data.get('selling_points_cn') or [],'prompts':data.get('prompts') or [],'images':images,'results':[{'status':'queued','url':''} for _ in range(count)],'status':'generating','analysisUpstreamUsed':used_analysis_upstream})
                        return json_response(self,200,data)
                        # Legacy serial fallback below is unreachable and retained for rollback reference.
                        # Two rounds: preferred provider -> alternate provider -> preferred provider.
                        # A response is accepted only after its JSON has enough usable prompts.
                        attempts=[(analysis_upstream,key)]
                        attempts.extend(analysis_fallbacks(analysis_upstream,store))
                        if len(attempts)>1: attempts.append((analysis_upstream,key))
                        data=None;normalized=[];used_analysis_upstream=analysis_upstream;last_problem=''
                        for attempt_no,(candidate_upstream,candidate_key) in enumerate(attempts,1):
                            used_analysis_upstream=candidate_upstream
                            if attempt_no>1: print(f'[analyze] 第 {attempt_no}/{len(attempts)} 次分析，切换至 {candidate_upstream}',flush=True)
                            status,payload=proxy('/v1/chat/completions',candidate_key,analysis_request,retries=1,timeout=360,base=ANALYSIS_UPSTREAMS[candidate_upstream])
                            print(f'[analyze] {candidate_upstream} 返回 status={status}',flush=True)
                            if status>=400:
                                last_problem=f'{candidate_upstream} HTTP {status}: {str(payload)[:220]}'
                                continue
                            try:
                                data,normalized=normalize_analysis_plan(payload,count)
                                break
                            except Exception as exc:
                                last_problem=f'{candidate_upstream} 返回内容不完整：{exc}'
                                print(f'[analyze] {last_problem}',flush=True)
                        if not normalized:
                            raise ValueError(f'两轮分析均未得到 {count} 条可用提示词。最后一次结果：{last_problem or "上游未返回有效内容"}')
                        data['prompts']=normalized
                        data['analysisUpstreamUsed']=used_analysis_upstream
                        data['generationId']=str(body.get('generationId') or f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}");data['outputFolder']=str(generation_folder(self.client_address[0],data['generationId']))
                        if not body.get('analysisOnly'): history_merge({'id':data['generationId'],'createdAt':time.strftime('%Y-%m-%dT%H:%M:%S'),'generationId':data['generationId'],'ip':str(self.client_address[0]),'model':str(body.get('model') or 'gpt-image-2'),'aspect':str(body.get('aspect') or '1:1'),'userPrompt':user,'selling_points_cn':data.get('selling_points_cn') or [],'prompts':data.get('prompts') or [],'images':images,'results':[{'status':'queued','url':''} for _ in range(count)],'status':'generating'})
                        return json_response(self,200,data)
                    finally:
                        ANALYZE_SEM.release()
                        print(f"[analyze] 释放锁, ip={self.client_address[0]}",flush=True)
                generation_id=str(body.get('generationId') or '')
                image_index=int(body.get('index') or 0)
                if self.path=='/api/query':
                    task_id=str(body.get('taskId') or '').strip()
                    if not task_id: raise ValueError('缺少 taskId')
                    endpoint=f"/v1/images/generations/{urllib.parse.quote(task_id)}"
                    status,payload=proxy(endpoint,key,None,'GET',base=image_base)
                else:
                    endpoint=str(body.pop('endpoint') or '/v1/images/generations');body.pop('index',None);body.pop('generationId',None)
                    # Numbered planning labels are metadata, not part of the
                    # visual brief. Remove them at the final API boundary as
                    # well, including when an old history card is regenerated.
                    if 'prompt' in body:body['prompt']=strip_prompt_number_label(body.get('prompt'))
                    user_ctx=str(body.pop('userPrompt') or '');aspect_ctx=str(body.pop('aspect') or '');title_ctx=strip_prompt_number_label(body.pop('title') or '')
                    if requests_no_overlay_text(user_ctx,body.get('prompt')):
                        prompt_text=str(body.get('prompt') or '')
                        body['prompt']='HIGHEST PRIORITY — EXACT USER REQUEST: '+user_ctx+'\nFollow this user request over every conflicting instruction in the generated image prompt.\n\n'+prompt_text+'\n\nFINAL TEXT POLICY: The user requested no added text. Do not render any overlay copy, headline, caption, callout, label, logo, watermark, or typography. Remove all previously requested overlay text from this image. Preserve only the original physical dial markings and branding visible on the reference product.'
                    elif user_ctx:
                        body['prompt']='HIGHEST PRIORITY — EXACT USER REQUEST: '+user_ctx+'\nFollow this user request over every conflicting instruction in the generated image prompt. Preserve its explicit requirements exactly.\n\n'+str(body.get('prompt') or '')
                    if generation_id:
                        history_ensure({'id':generation_id,'generationId':generation_id,'createdAt':time.strftime('%Y-%m-%dT%H:%M:%S'),'ip':str(self.client_address[0]),'model':str(body.get('model') or 'gpt-image-2'),'aspect':aspect_ctx,'userPrompt':user_ctx,'selling_points_cn':[],'prompts':[{'title':title_ctx or '详情图','prompt':str(body.get('prompt') or '')}],'images':body.get('reference_images') or [],'results':[]})
                        if image_index>0:history_update_result(generation_id,image_index,{'status':'creating'})
                    if endpoint.endswith('generateContent'): body.pop('model',None)
                    prepared=prepare_api_body(body);status=0;payload={}
                    for create_attempt in range(3):
                        warm_request_images(prepared)
                        status,payload=proxy(endpoint,key,prepared,base=image_base)
                        if not (status>=400 and is_reference_fetch_error(payload) and create_attempt<2): break
                        if generation_id:
                            history_update_result(generation_id,image_index,{'status':'retrying','url':'','error':f'参考图下载暂时失败，自动重试 {create_attempt+1}/2'})
                        print(f'reference image fetch failed for {generation_id or "direct request"}, retrying create {create_attempt+1}/2 with alternate proxy',flush=True)
                        switch_image_proxy(prepared)
                        time.sleep(4*(create_attempt+1))
                    if status<400 and not extract_url(payload) and not extract_id(payload):
                        time.sleep(1);status,payload=proxy(endpoint,key,prepared,base=image_base)
                remote_url=extract_url(payload) or extract_b64(payload);saved_image=save_generated_image(remote_url,self.client_address[0],generation_id,image_index) if remote_url and generation_id and image_index else ('','');local_url,previous_local_url=saved_image
                if status<400 and not remote_url and not extract_id(payload):print(f'empty upstream result {self.path}: {str(payload)[:300]}',flush=True)
                err=''
                if isinstance(payload,dict):
                    pe=payload.get('error')
                    err=pe if isinstance(pe,str) else (json.dumps(pe,ensure_ascii=False) if pe else '')
                    if not err and str(payload.get('status','')).lower() in ('failed','failure','error'):err=str(payload.get('message') or payload.get('status'))
                if not err and status>=400:err=f'HTTP {status}'
                if status>=400:print(f'upstream {self.path} -> {status}: {str(payload)[:300]}',flush=True)
                status_str='success' if remote_url else ('error' if err else 'queued')
                updated_at=str(time.time_ns())
                if generation_id:history_update_result(generation_id,image_index,{'status':status_str,'url':local_url or remote_url,'sourceUrl':remote_url,'previousUrl':previous_local_url,'taskId':extract_id(payload),'error':err,'updatedAt':updated_at})
                return json_response(self,status,{'url':local_url or remote_url,'sourceUrl':remote_url,'previousUrl':previous_local_url,'taskId':extract_id(payload),'status':status_str,'error':err,'updatedAt':updated_at,'raw':payload})
        except Exception as e:return json_response(self,400,{'error':str(e)})
        json_response(self,404,{'error':'not found'})
    def log_message(self,fmt,*args):print(f'{self.address_string()} - {fmt%args}',flush=True)
if __name__=='__main__':
    DATA.mkdir(exist_ok=True);_history_load();print(f'Watch Studio: http://{HOST}:{PORT}');ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
