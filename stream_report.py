"""
Stream Report - how did the last stream run?

Reads TikTok LIVE Studio's own logs and makes a page with CPU / RAM / lag over the stream,
saved in the reports folder from config.json and opened in your browser.

Run:  py -3 stream_report.py                 (most recent stream)
      py -3 stream_report.py 2026-10-19      (the stream that started on that day)
"""
import csv
import glob
import html
import json
import os
import re
import sys
import webbrowser
from datetime import datetime, timedelta

import stream_config

LOGS = os.path.join(os.environ["APPDATA"], "TikTok LIVE Studio", "logs")
OUT_DIR = stream_config.folder("reports_folder", "Stream Reports")
CPU_MAXED = 90  # % - above this the PC can't keep up and things start to stutter
# While you're live, LIVE Studio only logs a reading when the CPU is too high (every 5-45 min),
# so two high readings up to this far apart count as one maxed-out stretch.
MAX_GAP = 3600

SERVER_TS = re.compile(r"^\[\d+:\d+:(\d{4}-\d\d-\d\d/\d\d:\d\d:\d\d):\d+:")
MAIN_TS = re.compile(r"^\[(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)")
FIELD = re.compile(r"(\w+):\s*([\d.]+)")


def server_time(line):
    m = SERVER_TS.match(line)
    return datetime.strptime(m.group(1), "%Y-%m-%d/%H:%M:%S") if m else None


def find_streams():
    """(start, end) of every stream in the server logs."""
    streams = []
    for path in sorted(glob.glob(os.path.join(LOGS, "*-server.txt"))):
        start = last = None
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                t = server_time(line)
                if not t:
                    continue
                last = t
                if "MediaSDKControllerImplV2::StartStream]" in line and not start:
                    start = t
                elif "MediaSDKControllerImplV2::StopStream [begin]" in line and start:
                    streams.append((start, t))
                    start = None
        if start:  # LIVE Studio was closed while still live
            streams.append((start, last))
    return streams


def read_metrics(t0, t1):
    points = []
    for path in glob.glob(os.path.join(LOGS, "LS-main*.log")):
        if datetime.fromtimestamp(os.path.getmtime(path)) < t0:
            continue
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "systemCPUUsage" not in line:
                    continue
                m = MAIN_TS.match(line)
                if not m:
                    continue
                t = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S")
                if not t0 <= t <= t1:
                    continue
                v = {k: float(x) for k, x in FIELD.findall(line[line.find("{"):])}
                p = {"t": t, "cpu": v.get("systemCPUUsage", 0) * 100}
                if "systemMemoryUsage" in v:  # the detailed reading, logged when CPU is high
                    p["ram"] = v["systemMemoryUsage"] * 100
                    p["app"] = v.get("appCPUUsage", 0) * 100
                    p["appmem"] = v.get("appMemory", 0) / 1024
                    for part in ("render", "encode", "pushStream", "mainWindow"):
                        p[part] = (v.get(part + "ModerateStutter", 0) + v.get(part + "SeriousStutter", 0)) / 10
                points.append(p)
    points.sort(key=lambda p: p["t"])
    dedup = []  # LIVE Studio often writes the same reading twice
    for p in points:
        if not dedup or (p["t"] - dedup[-1]["t"]).total_seconds() > 2 or p.keys() != dedup[-1].keys():
            dedup.append(p)
    return dedup


def app_log_rows(t0, t1):
    """(time, app, cpu %, MB) rows between t0 and t1 from the apps-<date>.csv files Fortnite Chaos
    writes every minute. The whole-PC row has the app name "_WHOLE PC ..." and RAM % in the MB column."""
    day = t0.date()
    while day <= t1.date():
        path = os.path.join(OUT_DIR, f"apps-{day:%Y-%m-%d}.csv")
        day += timedelta(days=1)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8", errors="ignore") as f:
            next(f, None)
            for line in f:
                parts = line.rstrip("\n").split(",")
                if len(parts) != 4:
                    continue
                try:
                    t = datetime.strptime(parts[0], "%Y-%m-%d %H:%M:%S")
                    cpu, mb = float(parts[2]), float(parts[3])
                except ValueError:
                    continue
                if t0 <= t <= t1:
                    yield t, parts[1], cpu, mb


def read_pc_log(t0, t1):
    """Whole-PC CPU % for every minute Fortnite Chaos was running: [(time, cpu %)], or [] if there's no log."""
    return [(t, cpu) for t, name, cpu, _ in app_log_rows(t0, t1) if name.startswith("_")]


def read_app_log(t0, t1):
    """Per-app CPU/memory while live, from the apps-<date>.csv files Fortnite Chaos writes every minute.
    Returns [(app, average CPU %, peak CPU %, peak MB)] busiest first, or [] if there's no log."""
    seen = {}
    minutes = set()
    for t, name, cpu, mb in app_log_rows(t0, t1):
        if name.startswith("_"):
            continue
        minutes.add(t)
        a = seen.setdefault(name, [0.0, 0.0, 0.0])
        a[0] += cpu
        a[1] = max(a[1], cpu)
        a[2] = max(a[2], mb)
    if not minutes:
        return []
    apps = [(name, total / len(minutes), peak, mb) for name, (total, peak, mb) in seen.items()]
    return sorted(apps, key=lambda a: -a[1])


def read_events(t0, t1):
    """Gifts and effects between t0 and t1, from the events-<date>.csv files Fortnite Chaos writes.
    [{t, who, gift, effect, seconds, mystery}] oldest first, leaving out the test panel."""
    events = []
    day = t0.date()
    while day <= t1.date():
        path = os.path.join(OUT_DIR, f"events-{day:%Y-%m-%d}.csv")
        day += timedelta(days=1)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8", errors="ignore", newline="") as f:
            for row in csv.DictReader(f):
                try:
                    t = datetime.strptime(row["time"], "%Y-%m-%d %H:%M:%S")
                    seconds = float(row["seconds"])
                except (KeyError, TypeError, ValueError):
                    continue
                if t0 <= t <= t1 and row.get("who") != "Test panel":
                    events.append({"t": t, "who": row.get("who") or "", "gift": row.get("gift") or "",
                                   "effect": row.get("effect") or "", "seconds": seconds,
                                   "mystery": row.get("mystery") == "1"})
    return events


def gifts_card(events):
    """The gift section of the report: who sent the most, which effects, and when."""
    if not events:
        return ('<div class="card"><h2>Gifts</h2><p>No gift log for this stream - '
                "Fortnite Chaos saves one while it's running (from 5 Nov 2026).</p></div>")
    who, effects = {}, {}
    for e in events:
        if e["who"]:
            who[e["who"]] = who.get(e["who"], 0) + 1
        name = e["effect"].split(":")[0]
        effects[name] = effects.get(name, 0) + 1

    def top(counts):
        return sorted(counts.items(), key=lambda kv: -kv[1])[:10]

    def rows(counts):
        return "".join(f"<tr><td>{html.escape(n)}</td><td>{c}</td></tr>" for n, c in top(counts))

    moments = "".join(f"<tr><td>{e['t']:%I:%M:%S %p}</td><td>{html.escape(e['who'] or 'Someone')}</td>"
                      f"<td>{html.escape(e['gift'])}</td><td>{html.escape(e['effect'])}</td></tr>" for e in events)
    return ('<div class="card"><h2>Gifts</h2>'
            f"<p>{len(events)} gift effects this stream. Cut them into clips with Chaos Clips.bat.</p>"
            f"<table><tr><th>Top gifters</th><th>Gifts</th></tr>{rows(who)}</table>"
            f"<table><tr><th>Effects</th><th>Times</th></tr>{rows(effects)}</table>"
            "<details><summary>Show every gift</summary>"
            f'<table><tr><th>Time</th><th>Who</th><th>Gift</th><th>Effect</th></tr>{moments}</table></details></div>')


def fmt_dur(seconds):
    m = int(round(seconds / 60))
    return f"{m // 60}h {m % 60:02d}m" if m >= 60 else f"{m} min"


def summarise(points, start, end, pc_log=()):
    cpu = [p["cpu"] for p in points]
    if pc_log:
        # Fortnite Chaos's per-minute log is far more complete than LIVE Studio's few readings, so use it:
        # each minute over the limit counts as a maxed-out minute.
        maxed = 60.0 * sum(1 for _, c in pc_log if c >= CPU_MAXED)
        first_maxed = next((t for t, c in pc_log if c >= CPU_MAXED), None)
        cpu += [c for _, c in pc_log]
    else:
        maxed = 0.0
        for a, b in zip(points, points[1:]):
            gap = (b["t"] - a["t"]).total_seconds()
            if gap <= MAX_GAP and a["cpu"] >= CPU_MAXED and b["cpu"] >= CPU_MAXED:
                maxed += gap
        first_maxed = next((p["t"] for p in points if p["cpu"] >= CPU_MAXED), None)
    detailed = [p for p in points if "ram" in p]
    s = {
        "duration": fmt_dur((end - start).total_seconds()),
        "cpu_avg": sum(cpu) / len(cpu),
        "cpu_peak": max(cpu),
        "maxed": maxed,
        "ram_peak": max((p["ram"] for p in detailed), default=None),
        "appmem": (detailed[0]["appmem"], detailed[-1]["appmem"]) if detailed else None,
        "output_stutter": max((max(p["render"], p["encode"], p["pushStream"]) for p in detailed), default=0),
        "window_stutter": max((p["mainWindow"] for p in detailed), default=0),
    }
    findings = []
    if maxed >= 600:
        findings.append(("bad", f"Your CPU was maxed out (over {CPU_MAXED}%) for about {fmt_dur(maxed)}"
                         + (f", starting around {first_maxed:%I:%M %p}" if first_maxed else "") +
                         ". That's what makes the stream and game stutter. Check Fortnite is on Performance mode with a "
                         "frame cap, and close background apps (Stream Doctor does both checks)."))
    elif s["cpu_peak"] >= CPU_MAXED:
        findings.append(("warn", f"CPU touched {s['cpu_peak']:.0f}% but didn't stay there - short hiccups at most."))
    else:
        findings.append(("good", f"CPU stayed under {CPU_MAXED}% the whole stream (peak {s['cpu_peak']:.0f}%)."))
    if s["ram_peak"] is not None and s["ram_peak"] >= 85:
        findings.append(("warn", f"RAM reached {s['ram_peak']:.0f}%. Close Discord/Steam/Epic Launcher while live."))
    if detailed:
        if s["output_stutter"] >= 1:
            findings.append(("bad", f"LIVE Studio's own encoding/upload stuttered (up to {s['output_stutter']:.0f}% of "
                             "frames) - viewers saw lag even if your game felt fine."))
        else:
            findings.append(("good", "LIVE Studio's encoding and upload stayed clean - when it lagged, it was the PC "
                             "being overloaded, not the internet or the encoder."))
    if not detailed and s["cpu_peak"] < CPU_MAXED:
        findings.append(("good", "LIVE Studio never logged a 'CPU too high' warning."))
    return s, findings


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Stream Report</title>
<style>
:root{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;
--axis:#c3c2b7;--border:rgba(11,11,11,.10);--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--good:#0ca30c;--warn:#fab219;--bad:#d03b3b}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;
--ink:#f0efec;--ink2:#c3c2b7;--grid:#2c2c2a;--axis:#383835;--border:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--s3:#199e70}}
:root[data-theme="dark"]{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#2c2c2a;
--axis:#383835;--border:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--s3:#199e70}
*{box-sizing:border-box}body{margin:0;background:var(--page);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1000px;margin:0 auto;padding:28px 16px 48px}
h1{font-size:24px;margin:0}.sub{color:var(--ink2);margin:2px 0 20px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin-bottom:16px}
.tile{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:14px 16px}
.tile .k{color:var(--ink2);font-size:13px}.tile .v{font-size:28px;font-weight:650;margin-top:2px}
.tile .n{color:var(--muted);font-size:12px}
.findings{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:6px 16px;margin-bottom:16px}
.f{display:flex;gap:10px;padding:10px 0;border-top:1px solid var(--grid)}.f:first-child{border-top:0}
.f .tag{flex:none;font-size:12px;font-weight:700;padding:1px 8px;border-radius:99px;height:fit-content;color:#0b0b0b}
.tag.good{background:var(--good);color:#fff}.tag.warn{background:var(--warn)}.tag.bad{background:var(--bad);color:#fff}
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px;margin-bottom:16px}
.card h2{font-size:16px;margin:0}.card p{margin:2px 0 10px;color:var(--ink2);font-size:13px}
.legend{display:flex;flex-wrap:wrap;gap:16px;font-size:13px;color:var(--ink2);margin-bottom:6px}
.legend span{display:flex;align-items:center;gap:6px}.legend i{width:16px;height:2px;border-radius:2px;display:inline-block}
.chart{position:relative}svg{display:block;overflow:visible}
.tip{position:absolute;pointer-events:none;background:var(--surface);border:1px solid var(--border);border-radius:8px;
padding:8px 10px;font-size:12px;box-shadow:0 4px 16px rgba(0,0,0,.15);display:none;white-space:nowrap;z-index:2}
.tip .row{display:flex;align-items:center;gap:6px}.tip b{font-size:13px;color:var(--ink)}.tip .time{color:var(--muted);margin-bottom:4px}
.tip i{width:12px;height:2px;border-radius:2px;display:inline-block}
details{margin-top:8px}summary{cursor:pointer;color:var(--ink2);font-size:13px}
table{border-collapse:collapse;width:100%;font-size:13px;margin-top:8px;font-variant-numeric:tabular-nums}
th,td{text-align:right;padding:4px 8px;border-bottom:1px solid var(--grid)}th:first-child,td:first-child{text-align:left}
th{color:var(--ink2);font-weight:600}.empty{color:var(--muted)}
</style></head><body><main>
<h1>Stream Report</h1><p class="sub">SUBTITLE</p>
<div class="tiles">TILES</div>
<div class="findings">FINDINGS</div>
<div class="card"><h2>CPU and RAM during the stream</h2>
<p>Readings from TikTok LIVE Studio's logs. The shaded band is when you were live. Over 90% CPU means the PC can't keep up.
While live, LIVE Studio only writes a reading when the CPU is high, so a gap means it wasn't flagged.</p>
<div class="legend"><span><i style="background:var(--s1)"></i>Whole PC CPU</span><span><i style="background:var(--s2)"></i>LIVE Studio CPU</span>
<span><i style="background:var(--s3)"></i>RAM used</span></div>
<div class="chart" id="chart"><div class="tip" id="tip"></div></div>
<details><summary>Show the readings as a table</summary><div id="table"></div></details></div>
APPS
</main><script>
const D=DATA;
const NS='http://www.w3.org/2000/svg',L=44,R=14,T=12,B=30;
const series=[['cpu','Whole PC CPU','--s1'],['app','LIVE Studio CPU','--s2'],['ram','RAM used','--s3']];
const t0=D.t0,t1=D.t1,chart=document.getElementById('chart'),tip=document.getElementById('tip');
const fmt=t=>new Date(t*1000).toLocaleTimeString([], {hour:'numeric',minute:'2-digit'});
let svg,W,H,cross;
const x=t=>L+(t-t0)/(t1-t0)*(W-L-R),y=v=>T+(1-v/100)*(H-T-B);
const el=(n,a)=>{const e=document.createElementNS(NS,n);for(const k in a)e.setAttribute(k,a[k]);svg.appendChild(e);return e};
function draw(){  // drawn at the real width so the text stays readable on any screen
  W=Math.max(280,chart.clientWidth);H=Math.round(Math.min(340,Math.max(220,W*.38)));
  if(svg)svg.remove();
  svg=document.createElementNS(NS,'svg');svg.setAttribute('viewBox',`0 0 ${W} ${H}`);svg.setAttribute('width',W);svg.setAttribute('height',H);
  svg.setAttribute('role','img');svg.setAttribute('aria-label','CPU and RAM percentage over the stream');chart.prepend(svg);
  el('rect',{x:x(D.live[0]),y:T,width:Math.max(0,x(D.live[1])-x(D.live[0])),height:H-T-B,fill:'var(--s1)','fill-opacity':.06});
  for(const v of [0,25,50,75,100]){el('line',{x1:L,x2:W-R,y1:y(v),y2:y(v),stroke:v?'var(--grid)':'var(--axis)','stroke-width':1});
   const t=el('text',{x:L-8,y:y(v)+4,'text-anchor':'end','font-size':11,fill:'var(--muted)'});t.textContent=v+'%';}
  el('line',{x1:L,x2:W-R,y1:y(90),y2:y(90),stroke:'var(--axis)','stroke-width':1});
  const lim=el('text',{x:W-R,y:y(90)-5,'text-anchor':'end','font-size':11,fill:'var(--muted)'});lim.textContent='90% - maxed out';
  const span=t1-t0,ticks=Math.max(2,Math.floor((W-L-R)/90)),step=[900,1800,3600,7200,10800].find(s=>span/s<=ticks)||21600;
  for(let t=Math.ceil(t0/step)*step;t<=t1;t+=step){const e=el('text',{x:x(t),y:H-8,'text-anchor':'middle','font-size':11,fill:'var(--muted)'});e.textContent=fmt(t);}
  for(const [k,,c] of series){
    const pts=D.points.filter(p=>p[k]!=null);if(!pts.length)continue;
    let d='',prev=null;
    for(const p of pts){d+=(prev&&p.t-prev.t<=3600?'L':'M')+x(p.t).toFixed(1)+' '+y(p[k]).toFixed(1);prev=p;}
    el('path',{d,fill:'none',stroke:`var(${c})`,'stroke-width':2,'stroke-linejoin':'round','stroke-linecap':'round'});
    if(pts.length<60)for(const p of pts)el('circle',{cx:x(p.t),cy:y(p[k]),r:4,fill:`var(${c})`,stroke:'var(--surface)','stroke-width':2});
  }
  cross=el('line',{y1:T,y2:H-B,stroke:'var(--axis)','stroke-width':1,visibility:'hidden'});
  svg.addEventListener('pointermove',show);svg.addEventListener('pointerleave',hide);
}
function show(ev){
  const r=svg.getBoundingClientRect(),sx=ev.clientX-r.left;
  if(sx<L||sx>W-R){hide();return}
  const t=t0+(sx-L)/(W-L-R)*(t1-t0);let best=D.points[0];
  for(const p of D.points)if(Math.abs(p.t-t)<Math.abs(best.t-t))best=p;
  cross.setAttribute('x1',x(best.t));cross.setAttribute('x2',x(best.t));cross.setAttribute('visibility','visible');
  tip.replaceChildren();const h=document.createElement('div');h.className='time';h.textContent=fmt(best.t);tip.appendChild(h);
  for(const [k,n,c] of series){if(best[k]==null)continue;const row=document.createElement('div');row.className='row';
    const i=document.createElement('i');i.style.background=`var(${c})`;const b=document.createElement('b');b.textContent=Math.round(best[k])+'%';
    const s=document.createElement('span');s.textContent=n;row.append(i,b,s);tip.appendChild(row);}
  tip.style.display='block';
  tip.style.left=Math.min(W-tip.offsetWidth,Math.max(0,x(best.t)+12))+'px';tip.style.top='10px';
}
function hide(){tip.style.display='none';if(cross)cross.setAttribute('visibility','hidden')}
draw();let rt;addEventListener('resize',()=>{clearTimeout(rt);rt=setTimeout(draw,100)});
const tb=document.createElement('table'),hr=tb.insertRow();
for(const h of ['Time','Whole PC CPU','LIVE Studio CPU','RAM used','LIVE Studio window lag']){const th=document.createElement('th');th.textContent=h;hr.appendChild(th);}
for(const p of D.points){const r=tb.insertRow();
  for(const v of [fmt(p.t),p.cpu,p.app,p.ram,p.mainWindow]){const c=r.insertCell();
    if(typeof v==='string')c.textContent=v;else if(v==null){c.textContent='-';c.className='empty'}else c.textContent=Math.round(v)+'%';}}
document.getElementById('table').appendChild(tb);
</script></body></html>"""


def report_path(start):
    return os.path.join(OUT_DIR, f"stream-report-{start:%Y-%m-%d_%H%M}.html")


def make_missing():
    """Makes a report for every past stream that doesn't have one, without opening them.
    Skips a stream that ended in the last 30 minutes, in case it's still going."""
    made = 0
    for start, end in find_streams():
        if not os.path.exists(report_path(start)) and (datetime.now() - end).total_seconds() > 1800:
            made += bool(make_report(start, end, False))
    print(f"Made {made} missing report(s).")


def main():
    streams = find_streams()
    if not streams:
        sys.exit("No streams found in TikTok LIVE Studio's logs.")
    if "--missing" in sys.argv:
        return make_missing()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        day = args[0]
        streams = [s for s in streams if s[0].strftime("%Y-%m-%d") == day] or sys.exit(f"No stream started on {day}.")
    start, end = streams[-1]
    if not make_report(start, end, "--no-open" not in sys.argv):
        sys.exit("LIVE Studio didn't log any CPU readings for that stream.")


def make_report(start, end, open_it):
    """Writes the page for one stream. Returns its path, or None if there are no readings for it."""
    points = read_metrics(start - timedelta(minutes=15), end + timedelta(minutes=5))
    if not points:
        return None
    pc_log = read_pc_log(start, end)
    s, findings = summarise(points, start, end, pc_log)

    def tile(k, v, n=""):
        return f'<div class="tile"><div class="k">{k}</div><div class="v">{v}</div><div class="n">{n}</div></div>'

    maxed_note = f"time over {CPU_MAXED}%" + (" (checked every minute)" if pc_log else " (LIVE Studio's readings only)")
    tiles = [tile("Stream length", s["duration"], f"{start:%I:%M %p} - {end:%I:%M %p}"),
             tile("CPU maxed out", fmt_dur(s["maxed"]) if s["maxed"] else "Never", maxed_note),
             tile("Peak CPU", f"{s['cpu_peak']:.0f}%", "highest reading")]
    if s["ram_peak"] is not None:
        tiles.append(tile("Peak RAM", f"{s['ram_peak']:.0f}%"))
    if s["appmem"]:
        tiles.append(tile("LIVE Studio memory", f"{s['appmem'][1]:.1f} GB", f"started at {s['appmem'][0]:.1f} GB"))
    apps = read_app_log(start, end)
    if apps:
        rows = "".join(f"<tr><td>{html.escape(n)}</td><td>{avg:.1f}%</td><td>{peak:.0f}%</td><td>{mb / 1024:.1f} GB</td></tr>"
                       for n, avg, peak, mb in apps[:15])
        apps_html = ('<div class="card"><h2>Which apps were using the PC</h2>'
                     "<p>From Fortnite Chaos, which checks every minute while it's running. CPU is out of the whole PC.</p>"
                     "<table><tr><th>App</th><th>Average CPU</th><th>Peak CPU</th><th>Peak memory</th></tr>"
                     f"{rows}</table></div>")
        busiest = ", ".join(f"{n} {avg:.0f}%" for n, avg, _, _ in apps[:3])
        findings.insert(1, ("warn" if s["maxed"] >= 600 else "good", f"Busiest apps while live (average CPU): {busiest}."))
    else:
        apps_html = ('<div class="card"><h2>Which apps were using the PC</h2><p>No app log for this stream - '
                     "Fortnite Chaos writes one every minute while it's running (from 22 Oct 2026).</p></div>")
    labels = {"good": "Good", "warn": "Heads up", "bad": "Problem"}
    findings_html = "".join(f'<div class="f"><span class="tag {lvl}">{labels[lvl]}</span><span>{html.escape(txt)}</span></div>'
                            for lvl, txt in findings)
    data = {"t0": points[0]["t"].timestamp(), "t1": max(points[-1]["t"], end).timestamp(),
            "live": [start.timestamp(), end.timestamp()],
            "points": [{"t": p["t"].timestamp(), **{k: round(v, 1) for k, v in p.items() if k != "t"}} for p in points]}
    page = (PAGE.replace("SUBTITLE", f"{start:%A %d %B %Y}, live from {start:%I:%M %p} to {end:%I:%M %p}")
            .replace("TILES", "".join(tiles)).replace("FINDINGS", findings_html)
            .replace("DATA", json.dumps(data))
            # app and gifter names last: they could contain "DATA"
            .replace("APPS", gifts_card(read_events(start, end)) + apps_html))
    os.makedirs(OUT_DIR, exist_ok=True)
    out = report_path(start)
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print("Saved", out)
    for lvl, txt in findings:
        print(f"  [{labels[lvl]}] {txt}")
    if open_it:
        webbrowser.open(out)
    return out


if __name__ == "__main__":
    main()
