import machine
import socket
import uerrno
import uos
import time

# ================== 配置区 ==================
DEBUG_PIN = 16                  # GPIO16 调试按键
DEBUG_LEVEL = 0                 # 按下为低电平
UPLOAD_DIR = "/"                # 上传到根目录
MAX_FILE_SIZE = 2 * 1024 * 1024 # 单文件最大 2MB
# ==========================================

# ---------- GPIO16 内部上拉 ----------
pin = machine.Pin(DEBUG_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
time.sleep_ms(200)

# ================== MIME 类型 ==================
def content_type(path):
    if path.endswith(".html"): return b"text/html"
    if path.endswith(".js"): return b"application/javascript"
    if path.endswith(".css"): return b"text/css"
    if path.endswith(".png"): return b"image/png"
    if path.endswith(".jpg") or path.endswith(".jpeg"): return b"image/jpeg"
    if path.endswith(".gif"): return b"image/gif"
    if path.endswith(".ico"): return b"image/x-icon"
    if path.endswith(".json"): return b"application/json"
    if path.endswith(".txt"): return b"text/plain"
    return b"application/octet-stream"

# ================== 响应封装 ==================
def send_response(cl, status, body, ct=b"text/html"):
    cl.send(b"HTTP/1.1 " + status + b"\r\n")
    cl.send(b"Content-Type: " + ct + b"\r\n")
    cl.send(b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n")
    cl.send(body)

def send_404(cl):
    send_response(cl, b"404 Not Found", b"404 Not Found", b"text/plain")
    cl.close()

# ================== 上传页 HTML（内置，不用你做） ==================
UPLOAD_HTML = b"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>ESP32 File Upload</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;}
body{
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460);
  min-height:100vh;
  display:flex;align-items:center;justify-content:center;
  color:#fff;
}
.container{
  background:rgba(255,255,255,0.08);backdrop-filter:blur(10px);
  border-radius:20px;padding:40px;max-width:520px;width:90%;
  border:1px solid rgba(255,255,255,0.15);
}
h1{font-size:24px;margin-bottom:8px;background:linear-gradient(90deg,#00d2ff,#3a7bd5);-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.subtitle{color:#aaa;font-size:14px;margin-bottom:30px;}
.drop-zone{
  border:2px dashed rgba(255,255,255,0.3);border-radius:12px;
  padding:40px 20px;cursor:pointer;transition:all .3s;
}
.drop-zone:hover,.drop-zone.dragover{border-color:#00d2ff;background:rgba(0,210,255,0.08);}
.drop-zone .icon{font-size:48px;margin-bottom:12px;}
.drop-zone p{color:#ccc;font-size:14px;}
.drop-zone .hint{color:#666;font-size:12px;margin-top:8px;}
input[type=file]{display:none;}
.file-list{max-height:150px;overflow-y:auto;margin-bottom:20px;}
.file-item{
  background:rgba(255,255,255,0.1);padding:8px 12px;border-radius:8px;
  margin-bottom:6px;font-size:13px;display:flex;justify-content:space-between;
}
.file-item .size{color:#888;font-size:12px;}
.btn{
  background:linear-gradient(90deg,#00d2ff,#3a7bd5);color:#fff;
  border:none;padding:12px 36px;border-radius:30px;font-size:15px;
  cursor:pointer;transition:transform .2s;
}
.btn:hover{transform:scale(1.05);}
.btn:disabled{opacity:.4;cursor:not-allowed;}
.progress-bar{height:6px;background:rgba(255,255,255,0.1);border-radius:3px;margin-top:16px;overflow:hidden;display:none;}
.progress-bar .fill{height:100%;width:0%;background:linear-gradient(90deg,#00d2ff,#3a7bd5);transition:width .3s;}
.status{margin-top:16px;font-size:13px;min-height:20px;}
.status.success{color:#4ade80;}
.status.error{color:#f87171;}
.file-list-view{margin-top:24px;border-top:1px solid rgba(255,255,255,0.1);padding-top:16px;}
.file-list-view h3{font-size:14px;color:#888;margin-bottom:8px;}
.file-row{display:flex;justify-content:space-between;padding:4px 0;font-size:13px;color:#ccc;border-bottom:1px solid rgba(255,255,255,0.05);}
</style>
</head>
<body>
<div class="container">
<h1>ESP32 File Upload</h1>
<p class="subtitle">PS4CSS &middot; GPIO16 Debug Mode</p>

<div class="drop-zone" id="dz">
  <div class="icon">&#8682;</div>
  <p>点击选择文件，或拖拽到此处</p>
  <p class="hint">支持 html / js / css / png / jpg</p>
  <input type="file" id="fi" multiple>
</div>

<div class="file-list" id="fl"></div>
<button class="btn" id="ub" disabled>开始上传</button>

<div class="progress-bar" id="pb"><div class="fill" id="pf"></div></div>
<div class="status" id="st"></div>

<div class="file-list-view" id="fv" style="display:none;">
  <h3>ESP32 现有文件</h3>
  <div id="ef"></div>
</div>
</div>

<script>
const dz=document.getElementById('dz'),fi=document.getElementById('fi'),fl=document.getElementById('fl'),
      ub=document.getElementById('ub'),pb=document.getElementById('pb'),pf=document.getElementById('pf'),
      st=document.getElementById('st'),fv=document.getElementById('fv'),ef=document.getElementById('ef');

let files=[],total=0;

dz.onclick=()=>fi.click();
dz.ondragover=e=>{e.preventDefault();dz.classList.add('dragover');};
dz.ondragleave=()=>dz.classList.remove('dragover');
dz.ondrop=e=>{e.preventDefault();dz.classList.remove('dragover');addFiles(e.dataTransfer.files);};
fi.onchange=e=>addFiles(e.target.files);

function addFiles(fs){
  for(const f of fs){
    if(f.size>2 * 1024 * 1024){st.textContent=f.name+' 超过2MB';st.className='status error';return;}
    files.push(f);total+=f.size;
  }
  render();
}

function render(){
  fl.innerHTML=files.map((f,i)=>`<div class="file-item"><span>${f.name}</span><span class="size">${f.size>1024?(f.size/1024).toFixed(1)+'KB':f.size+'B'}</span></div>`).join('');
  ub.disabled=files.length===0;
}

ub.onclick=async()=>{
  ub.disabled=true;pb.style.display='block';let done=0;
  for(const f of files){
    st.textContent='上传: '+f.name;
    const buf=await f.arrayBuffer();
    const xhr=new XMLHttpRequest();
    xhr.open('POST','/upload/'+encodeURIComponent(f.name));
    xhr.setRequestHeader('Content-Type','application/octet-stream');
    await new Promise(r=>{
      xhr.upload.onprogress=e=>{
        if(e.lengthComputable) pf.style.width=Math.round((done+e.loaded)/total*100)+'%';
      };
      xhr.onload=()=>{done+=f.size;pf.style.width=Math.round(done/total*100)+'%';r();};
      xhr.send(buf);
    });
  }
  st.textContent='上传完成 ('+files.length+' 个文件)';st.className='status success';
  files=[];total=0;render();loadFiles();
};

function loadFiles(){
  fetch('/list').then(r=>r.json()).then(list=>{
    if(!list.length)return;fv.style.display='block';
    ef.innerHTML=list.map(f=>'<div class="file-row"><span>'+f.name+'</span><span>'+(f.size>1024?(f.size/1024).toFixed(1)+'KB':f.size+'B')+'</span></div>').join('');
  });
}
loadFiles();
</script>
</body>
</html>"""

# ================== 请求解析 ==================
def parse_req(req):
    lines = req.split("\r\n")
    method, path, _ = lines[0].split(" ")
    headers = {}
    body_start = req.find("\r\n\r\n") + 4
    for ln in lines[1:]:
        if ":" in ln:
            k, v = ln.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    return method, path, headers, body_start

def recv_full(cl, length):
    data = b""
    while len(data) < length:
        chunk = cl.recv(length - len(data))
        if not chunk:
            break
        data += chunk
    return data

# ================== 路由处理 ==================
def handle(cl, req):
    method, path, headers, body_start = parse_req(req)

    # 上传页
    if path == "/upload" and method == "GET":
        send_response(cl, b"200 OK", UPLOAD_HTML, b"text/html")
        return

    # 文件列表
    if path == "/list" and method == "GET":
        files = uos.listdir(UPLOAD_DIR)
        json = b"["
        for i, f in enumerate(files):
            sz = uos.stat(UPLOAD_DIR + "/" + f)[6]
            json += b'{"name":"' + f.encode() + b'","size":' + str(sz).encode() + b'}'
            if i < len(files) - 1: json += b","
        json += b"]"
        send_response(cl, b"200 OK", json, b"application/json")
        return

    # 文件上传
    if path.startswith("/upload/") and method == "POST":
        fname = path[8:].replace("%20", " ")
        length = int(headers.get("content-length", "0"))
        if length == 0 or length > MAX_FILE_SIZE:
            send_response(cl, b"400 Bad Request", b"Bad size", b"text/plain")
            return
        body = req[body_start:]
        while len(body) < length:
            body += cl.recv(length - len(body))
        with open(UPLOAD_DIR + "/" + fname, "wb") as f:
            f.write(body)
        print("Upload:", fname, len(body), "bytes")
        send_response(cl, b"200 OK", b"OK", b"text/plain")
        return

    # PS4 联网探测
    if path in ("/generate_204", "/connecttest.txt", "/ncsi.txt",
                "/check_network_status.txt", "/hotspot-detect.html", "/captiveportal.html"):
        cl.send(b"HTTP/1.1 204 No Content\r\n\r\n")
        return

    # 首页
    if path == "/" or path == "/index.html":
        try:
            with open("/index.html", "rb") as f:
                send_response(cl, b"200 OK", f.read(), b"text/html")
        except:
            send_404(cl)
        return

    # 静态文件
    try:
        with open(path, "rb") as f:
            body = f.read()
        cl.send(b"HTTP/1.1 200 OK\r\nContent-Type: ")
        cl.send(content_type(path))
        cl.send(b"\r\n\r\n")
        cl.send(body)
    except OSError as e:
        if e.args[0] == uerrno.ENOENT:
            send_404(cl)
        else:
            send_404(cl)
    except:
        send_404(cl)

# ================== HTTP 服务器 ==================
def start_server():
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", 80))
    s.listen(5)
    print("HTTP server running on http://10.0.0.10")
    print("Upload page: http://10.0.0.10/upload")

    while True:
        cl, addr = s.accept()
        try:
            req = cl.recv(4096).decode()
            if not req:
                cl.close()
                continue
            handle(cl, req)
        except Exception as e:
            print("Error:", e)
            try:
                send_404(cl)
            except:
                pass
        finally:
            try:
                cl.close()
            except:
                pass

# ================== 启动逻辑 ==================
if pin.value() == DEBUG_LEVEL:
    print("DEBUG MODE: REPL enabled.")
    print("Type start_server() to run manually.")
    print("Upload page: http://10.0.0.10/upload")
else:
    print("NORMAL MODE: Starting HTTP server...")
    start_server()