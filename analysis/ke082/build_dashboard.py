"""Render data/summary.json into a self-contained dashboard.html (Leaflet maps + Chart.js charts)."""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

TEMPLATE = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>KE082 루트·상층풍 분석</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root{color-scheme:light;
 --bg:#f6f6f4;--surface-1:#fcfcfb;--surface-2:#efefec;--border:#dcdbd6;
 --text-primary:#0b0b0b;--text-secondary:#52514e;--text-muted:#7c7b76;
 --s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;--s5:#e87ba4;--s6:#008300;--s7:#6250d6;--s8:#e34948;
 --head:#eb6834;--tail:#2a78d6;--neutral:#9a9994;--warn-bg:#fff4e5;--warn-fg:#7a4100}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;
 --bg:#111110;--surface-1:#1a1a19;--surface-2:#242423;--border:#33332f;
 --text-primary:#f0efec;--text-secondary:#c3c2b7;--text-muted:#8f8e86;
 --s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s6:#008300;--s7:#9085e9;--s8:#e66767;
 --head:#d95926;--tail:#3987e5;--warn-bg:#3a2a12;--warn-fg:#ffd59a}}
:root[data-theme="dark"]{color-scheme:dark;
 --bg:#111110;--surface-1:#1a1a19;--surface-2:#242423;--border:#33332f;
 --text-primary:#f0efec;--text-secondary:#c3c2b7;--text-muted:#8f8e86;
 --s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s6:#008300;--s7:#9085e9;--s8:#e66767;
 --head:#d95926;--tail:#3987e5;--warn-bg:#3a2a12;--warn-fg:#ffd59a}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text-primary);font:15px/1.5 -apple-system,"Segoe UI","Apple SD Gothic Neo","Noto Sans KR",sans-serif}
main{max-width:1180px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:32px 0 12px}
.sub{color:var(--text-secondary);margin:0 0 16px}
.banner{background:var(--warn-bg);color:var(--warn-fg);border-radius:8px;padding:12px 14px;margin:12px 0 20px;font-size:14px}
.banner ul{margin:6px 0 0 18px;padding:0}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
.tile{background:var(--surface-1);border:1px solid var(--border);border-radius:10px;padding:12px 14px}
.tile .k{font-size:12px;color:var(--text-secondary);text-transform:uppercase;letter-spacing:.04em}
.tile .v{font-size:26px;font-weight:600;line-height:1.2;margin-top:4px;font-variant-numeric:tabular-nums}
.tile .d{font-size:13px;color:var(--text-muted)}
.card{background:var(--surface-1);border:1px solid var(--border);border-radius:10px;padding:14px}
#map{height:460px;border-radius:8px;background:var(--surface-2)}
.legend{display:flex;flex-wrap:wrap;gap:8px 16px;margin:10px 0 0;font-size:13px}
.legend label{display:inline-flex;align-items:center;gap:6px;cursor:pointer;color:var(--text-secondary)}
.sw{width:18px;height:3px;border-radius:2px;display:inline-block}
.sw.dash{background:repeating-linear-gradient(90deg,var(--neutral) 0 4px,transparent 4px 7px)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.mini{height:170px;border-radius:6px;background:var(--surface-2)}
.card h3{margin:0 0 8px;font-size:15px;display:flex;justify-content:space-between;align-items:center}
.badge{font-size:11px;padding:2px 8px;border-radius:999px;background:var(--surface-2);color:var(--text-secondary);font-weight:500}
.badge.nrt{background:var(--s2);color:#fff}.badge.icn{background:var(--s3);color:#fff}.badge.none{border:1px dashed var(--border)}
dl{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;margin:8px 0 0;font-size:13px}
dt{color:var(--text-muted)}dd{margin:0;font-variant-numeric:tabular-nums}
.empty{color:var(--text-muted);font-size:13px;padding:10px 0}
.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}
.chart{height:280px;position:relative}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:7px 8px;text-align:left;border-bottom:1px solid var(--border);font-variant-numeric:tabular-nums;white-space:nowrap}
th{color:var(--text-secondary);font-weight:500}
.tw{overflow-x:auto}
.src{font-size:12px;color:var(--text-muted);margin-top:16px}
.leaflet-container{font:inherit}
</style>
</head>
<body>
<main>
<h1>KE082 (KAL82) 뉴욕 JFK → 인천 ICN 최근 7일 루트·상층풍 분석</h1>
<p class="sub" id="sub"></p>
<div id="banner" class="banner" hidden></div>

<div class="tiles" id="tiles"></div>

<h2>전체 루트 지도 (날짜별)</h2>
<div class="card">
 <div id="map"></div>
 <div class="legend" id="legend"></div>
</div>

<h2>날짜별 상세</h2>
<div class="grid" id="cards"></div>

<h2>차트</h2>
<div class="charts">
 <div class="card"><h3>최북단 위도 (°N) — 실제 트랙만</h3><div class="chart"><canvas id="c-lat"></canvas></div></div>
 <div class="card"><h3>순항 중 평균 정풍 성분 (kt, + 정풍 / − 배풍; 연한 막대 = 대권 기준선)</h3><div class="chart"><canvas id="c-hw"></canvas></div></div>
 <div class="card"><h3>경도별 정풍 성분 (kt)</h3><div class="chart"><canvas id="c-hwprof"></canvas></div></div>
 <div class="card"><h3>경도별 위도 (루트가 얼마나 북쪽인지)</h3><div class="chart"><canvas id="c-latprof"></canvas></div></div>
</div>

<h2>표</h2>
<div class="card tw"><table id="tbl"></table></div>
<p class="src" id="src"></p>
</main>

<script id="data" type="application/json">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const SLOTS = ['--s1','--s2','--s3','--s4','--s5','--s6','--s7','--s8'];
const F = D.flights;
const color = i => css(SLOTS[i % SLOTS.length]);
const fmt = (v, u='') => (v === undefined || v === null) ? '—' : (typeof v === 'number' ? v.toLocaleString('ko-KR') : v) + u;
const mins = m => m == null ? '—' : `${Math.floor(m/60)}h ${String(m%60).padStart(2,'0')}m`;
const AP = {KJFK:[40.6413,-73.7781,'JFK'],RKSI:[37.4602,126.4407,'ICN'],RJAA:[35.7720,140.3929,'NRT']};
const ulon = l => l < -30 ? l + 360 : l;
const lonLabel = v => v > 180 ? `${Math.round(360-v)}°W` : (v < 0 ? `${Math.round(-v)}°W` : `${Math.round(v)}°E`);

document.getElementById('sub').textContent =
 `JFK 출발일 기준 ${D.window.start} ~ ${D.window.end} · 생성 ${D.generated_utc} · 트랙 확보 ${D.summary.n_with_track}/${D.summary.n_flights}편 · 상층풍 계산 ${D.summary.n_with_winds}편`;

const unverified = F.filter(f => !f.verified).length;
const nRef = F.filter(f => f.track_source === 'great_circle_reference').length;
if (D.errors.length || D.summary.n_with_track < F.length) {
 const b = document.getElementById('banner'); b.hidden = false;
 b.innerHTML = `<strong>데이터 상태</strong>: Flightradar24 실제 트랙이 없는 날짜(${nRef}일)는 <em>JFK–ICN 대권항로를 기준선</em>으로 두고 그 날 그 시각의 상층풍(Open-Meteo 200/250/300 hPa)만 평가했습니다. 점선 = 기준선, 실선 = 실제 트랙. 실제 루트의 북상 정도는 트랙이 있어야 알 수 있습니다.` +
  (unverified ? ` ${unverified}개 행은 단일 출처(검색 스니펫)로 미검증입니다.` : '') +
  (D.errors.length ? `<details><summary>오류 ${D.errors.length}건</summary><ul>${D.errors.map(e=>`<li>${e}</li>`).join('')}</ul></details>` : '');
}

// ---- tiles
const S = D.summary;
const tiles = [
 ['최북단 루트', S.northernmost ? `${S.northernmost.max_lat}°N` : '—', S.northernmost ? `${S.northernmost.date} · ${lonLabel(ulon(S.northernmost.lon))}` : '트랙 없음'],
 ['최대 평균 정풍', S.strongest_headwind ? `${S.strongest_headwind.mean_kt} kt` : '—', S.strongest_headwind ? `${S.strongest_headwind.date} · 최대 ${S.strongest_headwind.max_kt} kt${nRef?' · 대권 기준':''}` : '상층풍 데이터 없음'],
 ['나리타(NRT) 회항', `${S.narita_dates.length}편`, S.narita_dates.length ? S.narita_dates.join(', ') : '확인된 회항 없음'],
 ['정상 인천 도착', `${F.filter(f=>f.destination_real==='RKSI' && f.status_text && f.status_text!=='unknown').length}편`, `미확인 ${F.filter(f=>!f.status_text || f.status_text==='unknown').length}편`],
];
document.getElementById('tiles').innerHTML = tiles.map(([k,v,d]) => `<div class="tile"><div class="k">${k}</div><div class="v">${v}</div><div class="d">${d}</div></div>`).join('');

// ---- maps
const dark = matchMedia('(prefers-color-scheme: dark)').matches && document.documentElement.dataset.theme !== 'light';
const baseTiles = () => L.tileLayer(`https://{s}.basemaps.cartocdn.com/${dark ? 'dark' : 'light'}_nolabels/{z}/{x}/{y}{r}.png`, {attribution:'© OpenStreetMap © CARTO', maxZoom:10});
const map = L.map('map', {worldCopyJump:false}).setView([52, 180], 3);
baseTiles().addTo(map);
const gcPts = (function(){const [a,b]=[AP.KJFK,AP.RKSI];const r=Math.PI/180;const p1=a[0]*r,l1=a[1]*r,p2=b[0]*r,l2=b[1]*r;
 const d=2*Math.asin(Math.sqrt(Math.sin((p2-p1)/2)**2+Math.cos(p1)*Math.cos(p2)*Math.sin((l2-l1)/2)**2));const out=[];
 for(let i=0;i<=120;i++){const f=i/120,A=Math.sin((1-f)*d)/Math.sin(d),B=Math.sin(f*d)/Math.sin(d);
  const x=A*Math.cos(p1)*Math.cos(l1)+B*Math.cos(p2)*Math.cos(l2),y=A*Math.cos(p1)*Math.sin(l1)+B*Math.cos(p2)*Math.sin(l2),z=A*Math.sin(p1)+B*Math.sin(p2);
  out.push([Math.atan2(z,Math.sqrt(x*x+y*y))/r, ulon(Math.atan2(y,x)/r)]);}return out;})();
L.polyline(gcPts, {color: css('--neutral'), weight: 1.5, dashArray: '4 5'}).addTo(map).bindTooltip('대권항로 (JFK–ICN 최단)');
map.fitBounds(L.latLngBounds(gcPts).pad(0.08));
for (const [k,[la,lo,n]] of Object.entries(AP)) L.circleMarker([la, ulon(lo)], {radius:5, color: css('--text-secondary'), fillColor: css('--surface-1'), fillOpacity:1, weight:2}).addTo(map).bindTooltip(n, {permanent:true, direction:'top'});
const layers = {}, windLayers = {};
const isRef = f => f.track_source === 'great_circle_reference';
// wind-field arrows (250 hPa) for one date: arrow length ∝ speed, one hue, darker = stronger
const windLayer = (f) => {
 const g = L.layerGroup();
 (f.wind_grid || []).forEach(w => {
  if (w.spd_kt == null) return;
  const r = Math.PI/180, len = Math.min(w.spd_kt, 150) / 150 * 4.5; // degrees of arrow length
  const toDir = (w.dir_deg + 180) % 360; // direction the air moves to
  const la = w.lat, lo = ulon(w.lon);
  const la2 = la + len * Math.cos(toDir*r), lo2 = lo + len * Math.sin(toDir*r) / Math.max(Math.cos(la*r), .2);
  const op = w.spd_kt > 100 ? .95 : w.spd_kt > 60 ? .7 : .4;
  const seg = L.polyline([[la, lo],[la2, lo2]], {color: css('--text-secondary'), weight: w.spd_kt > 100 ? 2.5 : 1.5, opacity: op});
  seg.bindTooltip(`${w.lat}°, ${lonLabel(lo)} · ${w.spd_kt} kt from ${Math.round(w.dir_deg)}°`);
  g.addLayer(seg); g.addLayer(L.circleMarker([la, lo], {radius: 1.5, color: css('--text-secondary'), opacity: op, fillOpacity: op}));
 });
 return g;
};
F.forEach((f, i) => {
 if (!f.lat_profile || !f.lat_profile.length) return;
 const pts = (f.wind_samples && f.wind_samples.length) ? f.wind_samples.map(s=>[s.lat, s.lon_unwrapped]) : f.lat_profile.map(p=>[p.lat, p.lon]);
 const line = L.polyline(pts, {color: color(i), weight: isRef(f) ? 2 : 2.5, opacity: .9, dashArray: isRef(f) ? '6 6' : null});
 line.bindTooltip(`${f.date}${isRef(f)?' (대권 기준선)':` · 최북단 ${f.max_lat}°N`}${f.headwind_mean_kt!=null?` · 평균 정풍 ${f.headwind_mean_kt} kt`:''}`, {sticky:true});
 layers[f.date] = line.addTo(map);
 if (f.headwind_max_at) L.circleMarker([f.headwind_max_at.lat, ulon(f.headwind_max_at.lon)], {radius:6, color: css('--surface-1'), weight:2, fillColor: color(i), fillOpacity:1}).addTo(map).bindTooltip(`${f.date} 최대 정풍 ${f.headwind_max_kt} kt`);
 if (f.wind_grid && f.wind_grid.length) windLayers[f.date] = windLayer(f);
});
const withGrid = F.filter(f => windLayers[f.date]);
document.getElementById('legend').innerHTML = F.map((f,i) => `<label><input type="checkbox" ${layers[f.date]?'checked':'disabled'} data-d="${f.date}"><span class="sw" style="background:${color(i)}${isRef(f)?';background:repeating-linear-gradient(90deg,'+color(i)+' 0 4px,transparent 4px 7px)':''}"></span>${f.date}${f.diverted_to_narita?' (NRT 회항)':''}${isRef(f)?' (기준선)':''}${layers[f.date]?'':' (트랙 없음)'}</label>`).join('') + `<label><span class="sw dash"></span>대권항로</label>` +
 (withGrid.length ? `<label>250 hPa 바람장: <select id="windsel"><option value="">숨김</option>${withGrid.map(f=>`<option value="${f.date}">${f.date}</option>`).join('')}</select></label>` : '');
document.getElementById('legend').addEventListener('change', e => {
 if (e.target.id === 'windsel') { Object.values(windLayers).forEach(l => map.removeLayer(l)); if (windLayers[e.target.value]) windLayers[e.target.value].addTo(map); return; }
 const l = layers[e.target.dataset.d]; if (l) e.target.checked ? l.addTo(map) : map.removeLayer(l); });
if (withGrid.length) { const sel = document.getElementById('windsel'); sel.value = withGrid[withGrid.length-1].date; windLayers[sel.value].addTo(map); }

// ---- per-date cards
const cards = document.getElementById('cards');
F.forEach((f, i) => {
 const dest = f.destination_real || '?';
 const badge = (f.diverted_to_narita ? '<span class="badge nrt">NRT 회항</span>' : (f.status_text && f.status_text!=='unknown' ? `<span class="badge icn">${dest==='RKSI'?'ICN 도착':dest}</span>` : '<span class="badge none">미확인</span>')) + (isRef(f) ? ' <span class="badge">대권 기준선</span>' : '');
 const el = document.createElement('div'); el.className = 'card';
 el.innerHTML = `<h3><span><span class="sw" style="background:${color(i)};vertical-align:middle;margin-right:6px"></span>${f.date}</span>${badge}</h3>
  <div class="mini" id="m-${i}"></div>` + (f.has_track ? `<dl>
  <dt>최북단</dt><dd>${f.max_lat}°N @ ${lonLabel(ulon(f.max_lat_lon))} (${f.max_lat_time_utc||''})</dd>
  <dt>비행거리</dt><dd>${fmt(f.distance_flown_nm,' nm')} (대권 대비 +${fmt(f.detour_pct,'%')})</dd>
  <dt>공중시간</dt><dd>${mins(f.airborne_min)}</dd>
  <dt>평균 정풍</dt><dd>${f.headwind_mean_kt!=null?fmt(f.headwind_mean_kt,' kt'):'풍속 데이터 없음'}${f.headwind_pacific_mean_kt!=null?` (태평양 구간 ${f.headwind_pacific_mean_kt} kt)`:''}</dd>
  <dt>최대 정풍</dt><dd>${f.headwind_max_kt!=null?`${f.headwind_max_kt} kt @ ${f.headwind_max_at.lat}°N, ${lonLabel(ulon(f.headwind_max_at.lon))}`:'—'}</dd>
  <dt>50kt 초과 정풍</dt><dd>${f.headwind_hours_over_50kt!=null?fmt(f.headwind_hours_over_50kt,' h'):'—'}</dd>
  <dt>평균 지상속도</dt><dd>${fmt(f.gs_mean_kt,' kt')} (최저 ${fmt(f.gs_min_kt,' kt')})</dd>
  <dt>기체</dt><dd>${fmt(f.registration)} ${fmt(f.aircraft)}</dd></dl>` : `<dl>
  <dt>상태</dt><dd>${f.status_text||'—'}</dd>
  ${f.headwind_mean_kt!=null?`<dt>평균 정풍*</dt><dd>${fmt(f.headwind_mean_kt,' kt')}${f.headwind_pacific_mean_kt!=null?` (태평양 구간 ${f.headwind_pacific_mean_kt} kt)`:''}</dd>
  <dt>최대 정풍*</dt><dd>${f.headwind_max_kt} kt @ ${f.headwind_max_at.lat}°N, ${lonLabel(ulon(f.headwind_max_at.lon))}</dd>
  <dt>최대 배풍*</dt><dd>${fmt(f.tailwind_max_kt,' kt')}</dd>
  <dt>50kt 초과 정풍*</dt><dd>${fmt(f.headwind_hours_over_50kt,' h')}</dd>
  <dt>최대 풍속*</dt><dd>${fmt(f.wind_speed_max_kt,' kt')}</dd>`:''}
  <dt>출발</dt><dd>${f.dep_real_utc?`실제 ${f.dep_real_utc}`:'—'}${f.dep_delay_min!=null?` (+${f.dep_delay_min}분)`:''}</dd>
  <dt>기체</dt><dd>${fmt(f.registration)} ${fmt(f.aircraft)}</dd>
  <dt>출처</dt><dd style="white-space:normal">${f.source||'—'}${f.verified?'':' · 미검증'}</dd></dl>
  <div class="empty">${f.notes||'Flightradar24 트랙 없음'}${f.headwind_mean_kt!=null?'<br>* JFK–ICN 대권항로 기준선 위의 상층풍 (실제 루트 아님)':''}</div>`);
 cards.appendChild(el);
 const m = L.map(`m-${i}`, {zoomControl:false, attributionControl:false, dragging:false, scrollWheelZoom:false}).setView([52,180],1);
 baseTiles().addTo(m);
 L.polyline(gcPts, {color: css('--neutral'), weight:1, dashArray:'3 4'}).addTo(m);
 if (layers[f.date]) { L.polyline(layers[f.date].getLatLngs(), {color: color(i), weight:2, dashArray: isRef(f) ? '5 5' : null}).addTo(m); m.fitBounds(layers[f.date].getBounds().pad(0.15)); }
 else { const dst = AP[f.destination_real] || AP.RKSI; m.fitBounds([[AP.KJFK[0], ulon(AP.KJFK[1])],[dst[0], ulon(dst[1])]], {padding:[10,10]}); }
});

// ---- charts
Chart.defaults.color = css('--text-secondary'); Chart.defaults.borderColor = css('--border'); Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
const labels = F.map(f => f.date.slice(5));
const barBase = {responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}}, scales:{x:{grid:{display:false}}, y:{grid:{color:css('--border')}, border:{display:false}}}};
new Chart(document.getElementById('c-lat'), {type:'bar', data:{labels, datasets:[{label:'최북단 위도', data:F.map(f=>f.has_track?f.max_lat:null), backgroundColor:F.map((f,i)=>color(i)), borderRadius:4, barPercentage:.6}]},
 options:{...barBase, scales:{x:barBase.scales.x, y:{...barBase.scales.y, min:40, suggestedMax:80, title:{display:true,text:'°N'}}}, plugins:{legend:{display:false}, tooltip:{callbacks:{label:c=>` ${c.raw}°N @ ${lonLabel(ulon(F[c.dataIndex].max_lat_lon))}`}}}}});
new Chart(document.getElementById('c-hw'), {type:'bar', data:{labels, datasets:[{label:'평균 정풍', data:F.map(f=>f.headwind_mean_kt??null), borderColor:F.map(f=>(f.headwind_mean_kt??0)>=0?css('--head'):css('--tail')), borderWidth:F.map(f=>isRef(f)?2:0), backgroundColor:F.map(f=>((f.headwind_mean_kt??0)>=0?css('--head'):css('--tail')) + (isRef(f)?'66':'')), borderRadius:4, barPercentage:.6}]},
 options:{...barBase, scales:{x:barBase.scales.x, y:{...barBase.scales.y, title:{display:true,text:'kt'}}}, plugins:{legend:{display:false}, tooltip:{callbacks:{label:c=>` 평균 ${c.raw} kt · 최대 ${F[c.dataIndex].headwind_max_kt} kt`}}}}});
const lineOpts = (ytitle, xmin, xmax) => ({responsive:true, maintainAspectRatio:false, interaction:{mode:'nearest', intersect:false}, elements:{line:{borderWidth:2, tension:.25}, point:{radius:0, hitRadius:8}},
 plugins:{legend:{display:true, position:'bottom', labels:{boxWidth:14, boxHeight:3}}, tooltip:{callbacks:{title:items=>items.length?lonLabel(items[0].parsed.x):''}}},
 scales:{x:{type:'linear', reverse:true, min:xmin, max:xmax, title:{display:true,text:'경도 (비행 방향: JFK → 알래스카 → 날짜변경선 → 일본 → ICN)'}, ticks:{stepSize:20, callback:lonLabel}, grid:{display:false}}, y:{title:{display:true,text:ytitle}, grid:{color:css('--border')}, border:{display:false}}}});
new Chart(document.getElementById('c-hwprof'), {type:'line', data:{datasets:F.map((f,i)=>({f,i})).filter(o=>o.f.wind_samples&&o.f.wind_samples.length).map(o=>({label:o.f.date + (isRef(o.f)?' (기준선)':''), borderColor:color(o.i), borderDash: isRef(o.f) ? [6,4] : [], data:o.f.wind_samples.map(s=>({x:s.lon_unwrapped, y:s.headwind_kt}))}))}, options:lineOpts('kt (+ 정풍)', 120, 290)});
new Chart(document.getElementById('c-latprof'), {type:'line', data:{datasets:F.map((f,i)=>({f,i})).filter(o=>o.f.lat_profile&&o.f.lat_profile.length).map(o=>({label:o.f.date + (isRef(o.f)?' (기준선)':''), borderColor:color(o.i), borderDash: isRef(o.f) ? [6,4] : [], data:o.f.lat_profile.map(p=>({x:p.lon, y:p.lat}))}))}, options:lineOpts('위도 °N', 120, 290)});

// ---- table
const cols = [['날짜',f=>f.date],['기체',f=>`${fmt(f.registration)} ${fmt(f.aircraft)}`],['실제 출발 (UTC)',f=>fmt(f.dep_real_utc)],['실제 도착 (UTC)',f=>fmt(f.arr_real_utc)],['도착지',f=>f.destination_real||'?'],['블록시간',f=>mins(f.block_time_min)],['최북단',f=>f.has_track?`${f.max_lat}°N`:'—'],['비행거리',f=>fmt(f.distance_flown_nm,' nm')],['우회율',f=>f.detour_pct!=null?`+${f.detour_pct}%`:'—'],['평균 정풍',f=>f.headwind_mean_kt!=null?`${f.headwind_mean_kt} kt${isRef(f)?'*':''}`:'—'],['최대 정풍',f=>f.headwind_max_kt!=null?`${f.headwind_max_kt} kt${isRef(f)?'*':''}`:'—'],['최대 배풍',f=>f.tailwind_max_kt!=null?`${f.tailwind_max_kt} kt${isRef(f)?'*':''}`:'—'],['상태',f=>f.status_text||'—'],['검증',f=>f.verified?'FR24':'미검증']];
document.getElementById('tbl').innerHTML = `<thead><tr>${cols.map(c=>`<th>${c[0]}</th>`).join('')}</tr></thead><tbody>${F.map(f=>`<tr>${cols.map(c=>`<td>${c[1](f)}</td>`).join('')}</tr>`).join('')}</tbody>`;
document.getElementById('src').textContent = '* 표시 = 실제 트랙 없이 JFK–ICN 대권항로 기준선에서 계산. 정풍 성분 = 항공기 진행방향에 투영한 상층풍 (Open-Meteo 200/250/300 hPa, 순항고도에 가장 가까운 기압면). 트랙·시각 = Flightradar24. 대권항로 = JFK–ICN 최단거리 참고선. 경도 축은 태평양 횡단이 끊기지 않도록 서경을 +360° 처리.';
</script>
</body>
</html>
"""


def build(summary: dict, out_path: str) -> str:
    html = TEMPLATE.replace("__DATA__", json.dumps(summary, ensure_ascii=False).replace("</", "<\\/"))
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return out_path


if __name__ == "__main__":
    with open(os.path.join(HERE, "data", "summary.json")) as fh:
        s = json.load(fh)
    print(build(s, sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "dashboard.html")))
