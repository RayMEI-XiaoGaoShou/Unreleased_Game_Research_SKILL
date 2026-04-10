"""Quick test: verify WBI signing + Bilibili API reachability"""
import json, time, requests
from functools import reduce
from hashlib import md5
from urllib.parse import urlencode
from pathlib import Path

MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62,
    11, 36, 20, 34, 44, 52
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
}

TIMEOUT = 15

def get_mixin_key(img_key, sub_key):
    orig = img_key + sub_key
    return reduce(lambda s, i: s + orig[i], MIXIN_KEY_ENC_TAB, "")[:32]

def wbi_sign(params, img_key, sub_key):
    mixin_key = get_mixin_key(img_key, sub_key)
    params["wts"] = round(time.time())
    params = dict(sorted(params.items()))
    params = {k: "".join(filter(lambda c: c not in "!'()*", str(v))) for k, v in params.items()}
    query = urlencode(params)
    params["w_rid"] = md5((query + mixin_key).encode()).hexdigest()
    return params

# Load cookies
cookie_path = Path(r"c:\Users\happyelements\Desktop\未上线游戏分析 Skill\unreleased-game-research\credentials\bilibili.json")
cookies = json.loads(cookie_path.read_text("utf-8"))

sess = requests.Session()
sess.headers.update(HEADERS)
for k, v in cookies.items():
    sess.cookies.set(k, str(v), domain=".bilibili.com")

# Step 1: Get WBI keys
print("Step 1: Fetching WBI keys from /x/web-interface/nav ...")
try:
    resp = sess.get("https://api.bilibili.com/x/web-interface/nav", timeout=TIMEOUT)
    nav_data = resp.json()
    print(f"  Status: {resp.status_code}, code: {nav_data.get('code')}")
    wbi_img = nav_data.get("data", {}).get("wbi_img", {})
    img_url = wbi_img.get("img_url", "")
    sub_url = wbi_img.get("sub_url", "")
    img_key = img_url.rsplit("/", 1)[-1].split(".")[0] if img_url else ""
    sub_key = sub_url.rsplit("/", 1)[-1].split(".")[0] if sub_url else ""
    print(f"  img_key: {img_key[:16]}...")
    print(f"  sub_key: {sub_key[:16]}...")
except Exception as e:
    print(f"  FAILED: {e}")
    exit(1)

# Step 2: Get video info
bvid = "BV1bb6gByEjg"
print(f"\nStep 2: Fetching video info for {bvid} ...")
try:
    params = wbi_sign({"bvid": bvid}, img_key, sub_key)
    resp = sess.get("https://api.bilibili.com/x/web-interface/view", params=params, timeout=TIMEOUT)
    view_data = resp.json()
    print(f"  Status: {resp.status_code}, code: {view_data.get('code')}")
    if view_data.get("code") == 0:
        d = view_data["data"]
        print(f"  Title: {d.get('title')}")
        print(f"  AID: {d.get('aid')}")
        aid = d["aid"]
    else:
        print(f"  Message: {view_data.get('message')}")
        exit(1)
except Exception as e:
    print(f"  FAILED: {e}")
    exit(1)

# Step 3: Fetch first page of comments
print(f"\nStep 3: Fetching first page of comments (oid={aid}) ...")
try:
    params = wbi_sign({"oid": aid, "type": 1, "mode": 3, "next": 0}, img_key, sub_key)
    resp = sess.get("https://api.bilibili.com/x/v2/reply/main", params=params, timeout=TIMEOUT)
    reply_data = resp.json()
    print(f"  Status: {resp.status_code}, code: {reply_data.get('code')}")
    if reply_data.get("code") == 0:
        cursor = reply_data.get("data", {}).get("cursor", {})
        replies = reply_data.get("data", {}).get("replies") or []
        print(f"  Total comments: {cursor.get('all_count', '?')}")
        print(f"  Comments on this page: {len(replies)}")
        print(f"  is_end: {cursor.get('is_end')}")
        if replies:
            first = replies[0]
            print(f"  First comment: {first.get('content', {}).get('message', '')[:80]}...")
            print(f"  Likes: {first.get('like', 0)}")
    else:
        print(f"  Message: {reply_data.get('message')}")
except Exception as e:
    print(f"  FAILED: {e}")
    exit(1)

print("\n=== ALL TESTS PASSED ===")
