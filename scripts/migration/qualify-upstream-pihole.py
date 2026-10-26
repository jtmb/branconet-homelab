#!/usr/bin/env python3
"""Exact data-fenced Pi-hole DNS/CLI-auth checks; no writer restart or config changes."""
import argparse
import datetime
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import re
import uuid

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('pihole_state_contract',HERE/'verify-upstream-pihole-state.py')
state=importlib.util.module_from_spec(spec);spec.loader.exec_module(state)
PROGRAM=HERE/'pihole-functional-observer.sh'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original',action='store_true')
    parser.add_argument('--state-receipt',type=Path);parser.add_argument('--state-receipt-sha256',default='')
    parser.add_argument('--previous-functional-receipt',type=Path);parser.add_argument('--previous-functional-receipt-sha256',default='')
    parser.add_argument('--dns-target',action='append',default=[],help='Existing inspected external IPv4:port; repeat for every actual route')
    parser.add_argument('--output-dir',type=Path,required=True);parser.add_argument('--apply',action='store_true')
    args=parser.parse_args();state.need(args.apply and os.name=='posix','explicit_native_observation');os.umask(0o077)
    os.environ.pop('BRANCONET_MIGRATION_SUDO_PASSWORD',None)
    state.need(bool(args.state_receipt)==bool(args.state_receipt_sha256) and bool(args.previous_functional_receipt)==bool(args.previous_functional_receipt_sha256),'paired_receipts')
    state.need(not args.state_receipt if args.original else bool(args.state_receipt),'original_or_data_verified_candidate')
    data=None
    if args.original:image=state.cold.ORIGINAL_IMAGE;version='v6.8'
    else:
        data=state.load_receipt(args.state_receipt,args.state_receipt_sha256)
        state.need(data.get('status')=='completed' and data.get('phase')=='verify' and data.get('temporary_pod_deleted') is True
                   and data.get('original_rows_and_configuration_preserved') is True,'completed_data_preservation')
        image=data['writer']['image'];version='v6.8'
    state.need(len(args.dns_target)<=7,'bounded_dns_targets')
    for target in args.dns_target:
        address,separator,port=target.rpartition(':')
        state.need(separator and port.isdigit() and 1<=int(port)<=65535,'existing_dns_endpoint')
        ipaddress.IPv4Address(address)
    output=args.output_dir
    state.need(output.is_absolute() and output.resolve()==output and state.RUNTIME in output.parents
               and not any((p/'.git').exists() for p in [output,*output.parents]),'native_output')
    output.mkdir(mode=0o700,parents=True,exist_ok=True)
    state.need(output.stat().st_uid==os.getuid() and not output.stat().st_mode&0o077,'private_output')
    receipt={'schema_version':1,'application':'pihole','passed':False,'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'source_sha256':{p.name:state.sha(p) for p in [Path(__file__),PROGRAM,HERE/'verify-upstream-pihole-state.py']},
             'original_observation':args.original,'writer_scaled_or_restarted':False,'configuration_or_native_secrets_mutated':False,
             'user_password_login_or_reset':False,'native_cli_session_created':False,'own_session_deleted':False,
             'external_dns_target_count':len(args.dns_target),'external_routes_claimed':False,
             'raw_response_or_credentials_logged':False,'full_goal_complete':False}
    path=output/('pihole-functional-'+uuid.uuid4().hex+'.json')
    try:
        before=state.fence('verify',image);receipt['writer']=before
        receipt['clock_start']=state.clock_observation(before,before['pod_name'])
        if data:
            state.need(before==data['writer'],'same_data_verified_writer')
            receipt.update(state_receipt_sha256=args.state_receipt_sha256,cold_receipt_sha256=data['cold_receipt_sha256'])
        if args.previous_functional_receipt:
            previous=state.load_receipt(args.previous_functional_receipt,args.previous_functional_receipt_sha256)
            state.need(data and previous.get('passed') is True and previous.get('cold_receipt_sha256')==data['cold_receipt_sha256']
                       and previous['writer']['image']==image and previous['writer']['pod_uid']!=before['pod_uid']
                       and data.get('different_writer_pod_verified') is True,'independent_restart_verified')
            receipt.update(previous_functional_receipt_sha256=args.previous_functional_receipt_sha256,different_writer_pod_verified=True)
        service=state.get('service','pihole')
        state.need(service['metadata']['uid']=='d24761ff-af16-4079-b6f6-9d19b1de3f93' and service['spec']['type']=='ClusterIP'
                   and service['spec']['clusterIP']=='10.96.11.155'
                   and {(p['protocol'],p['port']) for p in service['spec']['ports']}>={('TCP',53),('UDP',53)},'original_dns_service')
        actual=state.call(['kubectl','-n','pihole','exec',before['pod_name'],'-c','pihole','--','pihole-FTL','--version']).decode().strip()
        state.need(actual==version,'actual_ftl_version')
        # This explicit phase creates one own transient API CLI session and
        # deletes it; the key is read only inside the existing application Pod.
        result=state.call(['kubectl','--request-timeout=240s','-n','pihole','exec','-i',before['pod_name'],'-c','pihole','--','sh','-s','--',version,*args.dns_target],PROGRAM.read_bytes(),timeout=260)
        proof=json.loads(result)
        state.need(proof.get('passed') is True and proof.get('own_session_deleted') is True
                   and proof.get('dns_checks')==4*(1+len(args.dns_target)) and proof.get('authenticated_reads')==6,'dns_authenticated_reads_and_own_logout')
        receipt.update(observation=proof,native_cli_session_created=True,own_session_deleted=True,actual_ftl_version=actual)
        state.need(state.fence('verify',image)==before,'same_writer_after_checks')
        receipt['clock_end']=state.clock_observation(before,before['pod_name']);state.clock_interval(receipt['clock_start'],receipt['clock_end'])
        if data:state.private(args.state_receipt,args.state_receipt_sha256)
        for name,digest in receipt['source_sha256'].items():state.need(state.sha(HERE/name)==digest,'source_retained')
        receipt['passed']=True
    except Exception as exc:
        receipt['failure']=str(exc) if isinstance(exc,ValueError) and re.fullmatch('[a-zA-Z0-9_.-]+',str(exc)) else type(exc).__name__
    receipt['completed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    with path.open('x') as out:json.dump(receipt,out,sort_keys=True,indent=2);out.write('\n')
    print(json.dumps({'passed':receipt['passed'],'receipt':str(path),'receipt_sha256':state.sha(path)}))
    return 0 if receipt['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
