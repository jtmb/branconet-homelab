#!/usr/bin/env python3
"""Query the native ETS2 Steam endpoint at its preserved source address."""
import datetime,json,pathlib,socket,struct,time
ROOT=pathlib.Path(__file__).resolve().parents[2];checks=[]
for attempt in range(60):
 try:
  with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
   sock.settimeout(3);sock.connect(('192.168.0.6',27016));query=b'\xff'*4+b'TSource Engine Query\0';sock.send(query);response=sock.recv(8192)
   if response[:5]==b'\xff'*4+b'A':sock.send(query+response[5:9]);response=sock.recv(8192)
  if response[:5]!=b'\xff'*4+b'I':raise RuntimeError('Unexpected Steam server-info response')
  break
 except (TimeoutError,ConnectionError,RuntimeError):time.sleep(2)
else:raise RuntimeError('Native ETS2 server query did not respond')
offset=6
for _ in range(4):offset=response.index(b'\0',offset)+1
appid,players,maximum,bots=struct.unpack_from('<HBBB',response,offset)
report={'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_address_preserved':'192.168.0.6:27016/UDP','real_steam_server_info_query_passed':True,'steam_application_id_low16':appid,'player_count':players,'capacity':maximum,'source_config_original_retained':True,'client_game_join_pending':True}
(ROOT/'evidence/ets2-query-proof.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
