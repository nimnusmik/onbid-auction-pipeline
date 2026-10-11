import os, sqlite3, json, requests

SERVICE_KEY = os.environ["ONBID_API_KEY"]
DETAIL_URL = "https://apis.data.go.kr/B010003/OnbidRlstDtlSrvc/getRlstDtlInf"

cltr_mng_no = "2024-1200-093587"
pbct_cdtn_no = "5498996"

base = f"{DETAIL_URL}?serviceKey={SERVICE_KEY}"
params = {"resultType": "json", "numOfRows": 1, "pageNo": 1,
          "cltrMngNo": cltr_mng_no, "pbctCdtnNo": pbct_cdtn_no}

res = requests.get(base, params=params, timeout=15)
item = res.json()["body"]["items"]["item"]
if isinstance(item, list):
    item = item[0]

# 서브 배열들의 실제 구조 출력
for k in ["sqmsList", "apslEvlClgList", "leasInfList", "rgstPrmrInfList"]:
    v = item.get(k)
    print(f"{k}: {type(v).__name__} → {json.dumps(v, ensure_ascii=False)[:300]}")