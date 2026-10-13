"""Tiny fictional 'Rack Manager' app: a rack page with Ports and Cabling tabs. In-memory only."""
import argparse
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Rack Manager</title><style>
body{font-family:Helvetica,Arial,sans-serif;margin:0;background:#f4f6f8}header{background:#16423c;color:#fff;padding:14px 24px;font-size:18px}
nav{padding:12px 24px 0}.tab{background:#e3ebe9;border:0;padding:9px 20px;margin-right:4px;border-radius:6px 6px 0 0;cursor:pointer;font-size:14px}
.tab.active{background:#fff;font-weight:bold}main{padding:0 24px 24px}section{background:#fff;padding:14px}table{border-collapse:collapse;width:100%}
th,td{padding:9px 12px;border-bottom:1px solid #e1e5ea;text-align:left;font-size:14px}th{background:#eef2f1}
.edit-btn{background:#16423c;color:#fff;border:0;border-radius:4px;padding:5px 12px;cursor:pointer}.bar{margin-bottom:10px;font-size:14px}</style></head>
<body><header>Rack Manager &rsaquo; @@KIND@@ @@HOLDER@@</header>
<nav><button class="tab active" id="tab-ports">Ports</button><button class="tab" id="tab-cabling">Cabling</button></nav>
<main><section id="ports"><table><thead><tr><th>Device</th><th>Port</th><th>Speed</th><th>Status</th></tr></thead><tbody>@@PORTS@@</tbody></table></section>
<section id="cabling" hidden><div class="bar">Cable type <select id="cable-type"><option>Copper</option><option>Fibre</option><option>DAC</option></select></div>
<table><thead><tr><th>From</th><th>To</th><th>Cable</th><th>Length</th><th></th></tr></thead><tbody>@@CONN@@</tbody></table></section></main>
<script>for(const t of ['ports','cabling']){document.getElementById('tab-'+t).onclick=()=>{for(const u of ['ports','cabling']){
document.getElementById(u).hidden=(u!==t);document.getElementById('tab-'+u).classList.toggle('active',u===t)}}}</script></body></html>"""
RESOURCES = ("ports", "connections")


class State:
    def __init__(self):
        self.lock, self.items, self.next_id = threading.Lock(), {r: {} for r in RESOURCES}, 1


def make_handler(state):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json"):
            data = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _res(self):
            parts = urllib.parse.urlparse(self.path).path.strip("/").split("/")
            return (parts[1], parts[2] if len(parts) > 2 else None) if parts[0] == "api" and len(parts) > 1 and parts[1] in RESOURCES else (None, None)

        def do_GET(self):
            res, _ = self._res()
            with state.lock:
                snap = {r: list(v.values()) for r, v in state.items.items()}
            if res:
                return self._send(200, json.dumps(snap[res]))
            url = urllib.parse.urlparse(self.path)
            if url.path == "/":
                q = urllib.parse.parse_qs(url.query)
                kind, holder = q.get("kind", ["rack"])[0], q.get("holder", [""])[0]
                snap = {r: [i for i in v if not holder or i.get("holder") == holder] for r, v in snap.items()}
                ports = "".join("<tr><td>%(device)s</td><td>%(port)s</td><td>%(speed)s</td><td>%(status)s</td></tr>" % p for p in snap["ports"]) \
                    or '<tr><td colspan="4">No ports</td></tr>'
                conn = "".join('<tr><td>%(from_port)s</td><td>%(to_port)s</td><td>%(cable)s</td><td>%(length)s</td>'
                               '<td><button class="edit-btn">Edit connection</button></td></tr>' % c for c in snap["connections"]) \
                    or '<tr><td colspan="5">No connections</td></tr>'
                page = PAGE.replace("@@PORTS@@", ports).replace("@@CONN@@", conn)
                return self._send(200, page.replace("@@KIND@@", "Cabinet" if kind == "cabinet" else "Rack").replace("@@HOLDER@@", holder or "(all)"), "text/html")
            self._send(404, "{}")

        def do_POST(self):
            res, _ = self._res()
            if not res:
                return self._send(404, "{}")
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            with state.lock:
                body["id"] = str(state.next_id)
                state.next_id += 1
                state.items[res][body["id"]] = body
            self._send(201, json.dumps(body))

        def do_DELETE(self):
            res, iid = self._res()
            with state.lock:
                gone = state.items[res].pop(iid, None) if res else None
            self._send(204 if gone else 404, "")
    return H


def serve(port=0, host="127.0.0.1"):
    return ThreadingHTTPServer((host, port), make_handler(State()))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, default=8765)
    srv = serve(ap.parse_args().port)
    print("Rack Manager demo app on http://127.0.0.1:%d" % srv.server_address[1], flush=True)
    srv.serve_forever()
