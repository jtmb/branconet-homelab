#!/usr/bin/env python3
"""Prove current Swarm DNS answers through all three supplied node addresses."""
import datetime
import json
import pathlib
import secrets
import socket
import struct

def main():
 results=[]
 for host in ['192.168.0.4','192.168.0.5','192.168.0.6']:
  for protocol in ['UDP','TCP']:
   identity=secrets.randbelow(65536)
   query=struct.pack('!HHHHHH',identity,0x0100,1,0,0,0)+b'\x07example\x03com\x00'+struct.pack('!HH',1,1)
   item={'host':host,'protocol':protocol,'query':'example.com A'}
   try:
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM if protocol=='UDP' else socket.SOCK_STREAM) as connection:
     connection.settimeout(4)
     if protocol=='UDP':connection.sendto(query,(host,53));response=connection.recv(4096)
     else:
      connection.connect((host,53));connection.sendall(struct.pack('!H',len(query))+query)
      def receive(length):
       data=b''
       while len(data)<length:
        part=connection.recv(length-len(data))
        if not part:raise RuntimeError('DNS connection closed')
        data+=part
       return data
      length=struct.unpack('!H',receive(2))[0];response=receive(length)
    returned,flags,questions,answers,authority,additional=struct.unpack('!HHHHHH',response[:12])
    item.update({'passed':returned==identity and bool(flags&0x8000) and (flags&15)==0 and answers>0,'rcode':flags&15,'answers':answers})
   except Exception as error:item.update({'passed':False,'error':type(error).__name__})
   results.append(item)
 report={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':results,'all_passed':all(r['passed'] for r in results)}
 path=pathlib.Path(__file__).resolve().parents[2]/'evidence/source-dns.json';path.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report))

if __name__=='__main__':main()
