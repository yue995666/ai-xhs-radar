#!/usr/bin/env python3
import json, math, os, time, urllib.parse, urllib.request, urllib.error
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

PORT=int(os.environ.get("PORT","8765"))
TOKEN=os.environ.get("TIKHUB_TOKEN","").strip()
ROOT=Path(__file__).resolve().parent
BASE="https://api.tikhub.io"
ENDPOINT="/api/v1/xiaohongshu/app_v2/search_notes"
CACHE_SECONDS=6*60*60
CACHE={"ts":0,"posts":None}

SEARCHES=[
("GPT","ChatGPT"),("Claude","Claude AI"),("Gemini","Gemini AI"),
("AI图片","AI绘画"),("AI办公","AI办公"),("AI工具","AI工具")
]

DEMO=[
{"id":"d1","category":"Claude","title":"用了 Claude 一个月，我才发现这个功能有多离谱","author":"效率研究所","likes":8231,"collects":6921,"comments":381,"score":96,"cover":"","url":"","reason":"低粉高收藏，教程型内容，适合做实操类图文。"},
{"id":"d2","category":"AI办公","title":"AI 做 PPT 真不用熬夜了，我把流程拆成了 5 步","author":"打工人AI手册","likes":6210,"collects":7318,"comments":244,"score":94,"cover":"","url":"","reason":"收藏高，说明实用性强，很适合做新手教程。"},
{"id":"d3","category":"GPT","title":"我发现 99% 的人都没用对 ChatGPT 的这个功能","author":"AI日常","likes":13520,"collects":8890,"comments":622,"score":93,"cover":"","url":"","reason":"标题信息差强，可以改成自己的真实测试版本。"}
]

def num(v):
    if isinstance(v,(int,float)): return int(v)
    s=str(v or "").strip().lower().replace(",","")
    try:
        if s.endswith("w") or s.endswith("万"): return int(float(s[:-1])*10000)
        if s.endswith("k"): return int(float(s[:-1])*1000)
        return int(float(s))
    except: return 0

def items(obj):
    if isinstance(obj,dict):
        arr=obj.get("items")
        if isinstance(arr,list):
            for x in arr:
                if isinstance(x,dict) and isinstance(x.get("note_card"),dict): yield x
        for v in obj.values():
            if isinstance(v,(dict,list)): yield from items(v)
    elif isinstance(obj,list):
        for v in obj: yield from items(v)

def cover(card):
    c=card.get("cover")
    if isinstance(c,dict):
        for k in ("url_default","url_pre","url"):
            u=c.get(k)
            if isinstance(u,str) and u.startswith("http"): return u
    imgs=card.get("image_list")
    if isinstance(imgs,list) and imgs:
        for img in imgs:
            if not isinstance(img,dict): continue
            for k in ("url_default","url_pre","url"):
                u=img.get(k)
                if isinstance(u,str) and u.startswith("http"): return u
            for info in img.get("info_list",[]) if isinstance(img.get("info_list"),list) else []:
                if isinstance(info,dict) and isinstance(info.get("url"),str): return info["url"]
    return ""

def normalize(item,category):
    card=item.get("note_card") or {}
    info=card.get("interact_info") if isinstance(card.get("interact_info"),dict) else {}
    user=card.get("user") if isinstance(card.get("user"),dict) else {}
    nid=str(item.get("id") or card.get("note_id") or card.get("id") or "")
    title=card.get("display_title") or card.get("title") or str(card.get("desc") or "")[:42] or "未命名笔记"
    likes=num(info.get("liked_count") or info.get("like_count"))
    collects=num(info.get("collected_count") or info.get("collect_count"))
    comments=num(info.get("comment_count") or info.get("comments_count"))
    score=round(min(99,18+math.log10(likes+1)*11+math.log10(collects+1)*15+math.log10(comments+1)*6))
    token=item.get("xsec_token") or ""
    url=f"https://www.xiaohongshu.com/explore/{urllib.parse.quote(nid)}" if nid else ""
    if url and token: url+="?"+urllib.parse.urlencode({"xsec_token":token,"xsec_source":"pc_search"})
    ratio=collects/max(likes,1)
    reason="收藏表现很强，优先研究教程结构和封面。" if ratio>=0.7 else "互动表现不错，适合参考选题、标题和内容结构。"
    return {"id":nid or f"{category}-{abs(hash(title))}","category":category,"title":title,"author":user.get("nickname") or "小红书作者","likes":likes,"collects":collects,"comments":comments,"score":score,"cover":cover(card),"url":url,"reason":reason}

def fetch_keyword(keyword):
    q=urllib.parse.urlencode({"keyword":keyword,"page":1,"sort_type":"collect_descending","note_type":"普通笔记","time_filter":"一天内","source":"explore_feed","ai_mode":0})
    req=urllib.request.Request(BASE+ENDPOINT+"?"+q,headers={"Authorization":f"Bearer {TOKEN}","Accept":"application/json","User-Agent":"AI-XHS-Radar/1.0"})
    with urllib.request.urlopen(req,timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))

def fetch_live():
    seen={}; errors=[]
    for category,keyword in SEARCHES:
        try:
            raw=fetch_keyword(keyword)
            code=raw.get("code")
            if code not in (None,200):
                errors.append(f"{keyword}: "+str(raw.get("message_zh") or raw.get("message") or code))
                continue
            got=0
            for item in items(raw.get("data",raw)):
                p=normalize(item,category); got+=1
                if p["id"] not in seen or p["score"]>seen[p["id"]]["score"]: seen[p["id"]]=p
            if not got: errors.append(f"{keyword}: 没解析到笔记")
        except Exception as e:
            errors.append(f"{keyword}: {type(e).__name__}")
    ps=sorted(seen.values(),key=lambda x:(x["score"],x["collects"],x["likes"]),reverse=True)
    return ps[:36],errors

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed=urllib.parse.urlparse(self.path)
        if parsed.path=="/healthz":
            return self.send_json({"ok":True})
        if parsed.path=="/api/radar":
            force=urllib.parse.parse_qs(parsed.query).get("force",["0"])[0]=="1"
            if not TOKEN:
                return self.send_json({"mode":"demo","posts":DEMO,"message":"线上服务已启动，但还没有配置 TikHub Token，目前显示演示数据。"})
            if CACHE["posts"] is not None and not force and time.time()-CACHE["ts"]<CACHE_SECONDS:
                return self.send_json({"mode":"live","posts":CACHE["posts"],"message":"正在使用 6 小时缓存，避免重复请求。"})
            posts,errors=fetch_live()
            if posts:
                CACHE["ts"],CACHE["posts"]=time.time(),posts
                msg=f"已更新真实数据，共筛选出 {len(posts)} 篇。"
                if errors: msg+=" 部分关键词未成功。"
                return self.send_json({"mode":"live","posts":posts,"message":msg})
            return self.send_json({"mode":"demo","posts":DEMO,"message":"TikHub 暂未拉到有效数据："+("；".join(errors[:2]) if errors else "暂无结果")})
        if parsed.path in ("","/"): self.path="/index.html"
        return super().do_GET()

    def send_json(self,obj,status=200):
        data=json.dumps(obj,ensure_ascii=False).encode("utf-8")
        self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(data))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(data)

if __name__=="__main__":
    os.chdir(ROOT)
    print(f"AI 小红书爆款雷达启动，端口 {PORT}")
    ThreadingHTTPServer(("0.0.0.0",PORT),Handler).serve_forever()
