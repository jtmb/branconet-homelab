#!/usr/bin/env python3
"""Build bounded readonly SQLite-native typed-row digests; no row values leave Pod."""
import json
import re

APPEND = {'addinfo_by_id','client_by_id','domain_by_id','forward_by_id','message','query_storage','session'}
REBUILT = ['domainlist_by_group','adlist_by_group','client_by_group','info']


def q(name):
    assert isinstance(name,str) and name and all(c.isalnum() or c=='_' for c in name)
    return '"'+name+'"'


def lit(text):
    return "'"+text.replace("'","''")+"'"


def digest_query(query):
    return 'hex(sha3_query('+query+'))'


def build(name, schema, baseline=None, previous=None):
    """One read transaction, constant-memory C hashing, explicit original columns."""
    assert name in ['gravity.db','pihole-FTL.db']
    columns=schema['table_xinfo']
    fields=[]
    for table,info in sorted(columns.items()):
        cols=[x['name'] for x in info]
        assert all(not x.get('hidden',0) for x in info)
        selected=','.join(q(c) for c in cols)
        order=','.join(str(i+1) for i in range(len(cols)))
        where=''
        cutoff='NULL'
        if name=='pihole-FTL.db' and table in APPEND:
            assert 'id' in cols
            if baseline is None:
                cutoff='COALESCE((SELECT MAX(id) FROM '+q(table)+'),0)'
            else:
                value=baseline['tables'][table]['cutoff'];assert isinstance(value,int) and 0<=value<2**63
                cutoff=str(value)
            prefix='SELECT '+selected+' FROM '+q(table)+' WHERE "id"<='
            query=lit(prefix)+'||CAST('+cutoff+' AS TEXT)||'+lit(' ORDER BY "id"')
            prefix_count='(SELECT COUNT(*) FROM '+q(table)+' WHERE id<='+cutoff+')'
        else:
            if name=='pihole-FTL.db' and table=='ftl':
                where=' WHERE "id"<>1'
            elif name=='pihole-FTL.db' and table in ['counters','network','network_addresses','sqlite_sequence']:
                # Separately typed, identity-bound rows/counters below; whole-row
                # digests remain measured rather than falsely called equivalent.
                pass
            query=lit('SELECT '+selected+' FROM '+q(table)+where+' ORDER BY '+order)
            prefix_count='(SELECT COUNT(*) FROM '+q(table)+where+')'
        checkpoint=''
        if name=='pihole-FTL.db' and table in APPEND:
            maximum='COALESCE((SELECT MAX(id) FROM '+q(table)+'),0)'
            current_query=lit(prefix)+'||CAST('+maximum+' AS TEXT)||'+lit(' ORDER BY "id"')
            checkpoint=",'checkpoint_cutoff',"+maximum+",'checkpoint_digest',"+(digest_query(current_query) if baseline else 'NULL')
            if previous:
                prior=previous['tables'][table]['checkpoint_cutoff'];assert isinstance(prior,int) and 0<=prior<2**63
                prior_query=lit(prefix+str(prior)+' ORDER BY "id"')
                checkpoint+=",'previous_checkpoint_count',(SELECT COUNT(*) FROM "+q(table)+' WHERE id<='+str(prior)+"),'previous_checkpoint_digest',"+digest_query(prior_query)
        fields.append(lit(table)+",json_object('count',(SELECT COUNT(*) FROM "+q(table)+"),'original_count',"+prefix_count+",'cutoff',"+cutoff+",'digest',"+digest_query(query)+checkpoint+')')
    fields=','.join(fields)
    tables='json_object('+fields+')'
    objects="(SELECT json_group_array(json_object('type',type,'name',name,'tbl_name',tbl_name,'sql',sql)) FROM (SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_autoindex%' ORDER BY type,name))"
    xinfo=[]
    for table in sorted(columns):
        xinfo.append(lit(table)+",json((SELECT json_group_array(json_object('cid',cid,'name',name,'type',type,'notnull',\"notnull\",'dflt_value',dflt_value,'pk',pk,'hidden',hidden)) FROM pragma_table_xinfo("+lit(table)+')))')
    result="json_object('tables',"+tables+",'schema',json("+objects+"),'table_xinfo',json_object("+','.join(xinfo)+")"
    if name=='gravity.db':
        result+=",'version',(SELECT CAST(value AS INTEGER) FROM info WHERE property='version'),'removed_stat_rows',(SELECT COUNT(*) FROM sqlite_stat1 WHERE tbl IN ("+','.join(lit(x) for x in REBUILT)+'))'
    else:
        result+=",'version',(SELECT CAST(value AS INTEGER) FROM ftl WHERE id=0)"
        result+=",'oldest_query_timestamp',(SELECT MIN(timestamp) FROM query_storage),'newest_query_timestamp',(SELECT MAX(timestamp) FROM query_storage)"
        result+=",'counter_rows',json((SELECT json_group_array(json_object('id',id,'value',value)) FROM (SELECT id,value FROM counters ORDER BY id)))"
        result+=",'last_timestamp',(SELECT value FROM ftl WHERE id=1)"
        result+=",'sequence_rows',json((SELECT json_group_array(json_object('name',name,'seq',seq)) FROM (SELECT name,seq FROM sqlite_sequence ORDER BY name)))"
        stable='SELECT id,hwaddr,interface,firstSeen,macVendor,aliasclient_id FROM network WHERE id='
        network_digest=digest_query(lit(stable)+"||CAST(id AS TEXT)")
        result+=",'network_rows',json((SELECT json_group_array(json_object('id',id,'stable_digest',"+network_digest+",'lastQuery',lastQuery,'numQueries',numQueries)) FROM (SELECT * FROM network ORDER BY id)))"
        address_key=digest_query(lit('SELECT network_id,ip FROM network_addresses WHERE ip=')+'||quote(ip)')
        address_name=digest_query(lit('SELECT name FROM network_addresses WHERE ip=')+'||quote(ip)')
        address_ip=digest_query(lit('SELECT ip FROM network_addresses WHERE ip=')+'||quote(ip)')
        result+=",'address_rows',json((SELECT json_group_array(json_object('key_digest',"+address_key+",'ip_digest',"+address_ip+",'network_id',network_id,'name_digest',"+address_name+",'lastSeen',lastSeen,'nameUpdated',nameUpdated)) FROM (SELECT * FROM network_addresses ORDER BY ip)))"
    result+=')'
    # PRAGMA hard_heap_limit applies to this isolated sqlite CLI process only.
    # JSON decoding consumes its bounded metadata result, never the huge tables.
    return """.bail on
.timeout 5000
.limit length 1048576
PRAGMA hard_heap_limit=134217728;
PRAGMA query_only=ON;
PRAGMA cache_size=-8192;
PRAGMA temp_store=MEMORY;
PRAGMA mmap_size=0;
BEGIN;
SELECT """+result+" AS snapshot;\nCOMMIT;\n"


def decode(data):
    text=data.decode('utf-8')
    text='\n'.join(line for line in text.splitlines() if not re.fullmatch(r'\s*length\s+1048576\s*',line))
    decoder=json.JSONDecoder();values=[]
    while text.strip():
        value,n=decoder.raw_decode(text.lstrip());values.append(value);text=text.lstrip()[n:]
    rows=[r for v in values if isinstance(v,list) for r in v if isinstance(r,dict) and 'snapshot' in r]
    assert len(rows)==1
    snapshot=json.loads(rows[0]['snapshot'])
    for row in snapshot['schema']:
        if row['sql'] is not None:row['sql']=' '.join(row['sql'].split())
    return snapshot
