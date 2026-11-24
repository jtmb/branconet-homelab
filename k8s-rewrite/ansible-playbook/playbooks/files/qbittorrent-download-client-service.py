"""Move the existing Radarr and Sonarr qBittorrent clients to the internal Service."""

import base64, json, subprocess, urllib.error, urllib.request, xml.etree.ElementTree as XML
NEW = "qbittorrent-webui.plex.svc.cluster.local"
OLD = "192.168.0.4"
def kube(*args):
    return subprocess.check_output(["kubectl","-n","plex",*args],timeout=12)
def request(addr,port,key,path,method="GET",body=None):
    url=f"http://{addr}:{port}/api/v3/downloadclient{path}"
    headers={"X-Api-Key":key,"Content-Type":"application/json","Accept":"application/json"}
    req=urllib.request.Request(url, None if body is None else json.dumps(body).encode(), headers, method=method)
    try:
        with urllib.request.urlopen(req,timeout=18) as response:
            return response.status,json.loads(response.read() or b"null")
    except urllib.error.HTTPError as exc:
        # Remote validation bodies may contain credential-bearing data.
        return exc.code,None
template='{{index .data "QBITTORRENT_USERNAME"}} {{index .data "QBITTORRENT_PASSWORD"}}'
canonical=tuple(base64.b64decode(value).decode() for value in kube("get","secret","qbittorrent-runtime","-o","go-template="+template).split())
prepared=[]
for name,port in [("radarr",7878),("sonarr",8989)]:
    addr=json.loads(kube("get","svc",name,"-o","json"))["spec"]["clusterIP"]
    key=XML.fromstring(kube("exec","deploy/"+name,"--","cat","/config/config.xml")).findtext("ApiKey")
    assert key
    code, item=request(addr,port,key,"/1")
    assert code == 200 and item["implementation"].casefold() == "qbittorrent" and item["enable"]
    fields={entry["name"]:entry for entry in item["fields"]}
    assert fields["host"]["value"] in (OLD,NEW) and fields["port"]["value"] == 8112 and not fields["useSsl"]["value"]
    assert fields["username"]["value"] == canonical[0], (name,"unexpected account")
    baseline=json.loads(json.dumps(item))
    fields["host"]["value"] = NEW
    fields["password"]["value"] = canonical[1]
    code,_=request(addr,port,key,"/test","POST",item)
    assert code in (200,204), (name,"prospective Service-path test",code)
    print(name,"prospective internal Service test passed",flush=True)
    prepared.append((name,addr,port,key,baseline,item))
for name,addr,port,key,baseline,item in prepared:
    code, current=request(addr,port,key,"/1")
    assert code == 200
    assert current == baseline, (name,"configuration changed during preflight")
    current_fields={entry["name"]:entry for entry in current["fields"]}
    current_host=current_fields["host"]["value"]
    if current_host != NEW:
        code,_=request(addr,port,key,"/1","PUT",item)
        assert code in (200,202,204), (name,"host update",code)
        print(name, "updated legacy address", flush=True)
    code,saved=request(addr,port,key,"/1")
    assert code == 200
    saved_fields={entry["name"]:entry for entry in saved["fields"]}
    assert saved_fields["host"]["value"] == NEW
    assert saved_fields["password"]["value"] == canonical[1] or (
        bool(saved_fields["password"]["value"]) and set(saved_fields["password"]["value"]) <= set("*•")
    ), (name,"unexpected credential representation")
    saved_fields["password"]["value"]=canonical[1]
    assert saved == item, (name,"non-credential settings differ")
    code,_=request(addr,port,key,"/test","POST",saved)
    assert code in (200,204), (name,"saved connection test",code)
    print(name,"saved and verified against the internal Service",flush=True)
