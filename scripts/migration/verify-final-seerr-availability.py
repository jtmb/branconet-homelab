#!/usr/bin/env python3
"""Read only exact changed Seerr status rows and their existing Plex/Sonarr items."""
import hashlib
import json
from pathlib import Path
import runpy

SOURCE=Path(__file__).resolve()
LIB=runpy.run_path(str(SOURCE.with_name('verify-final-media-history.py')))
OUT=LIB['OUT']

PAYLOAD=r'''
(async()=>{
 const input=JSON.parse(fs.readFileSync(0,'utf8'));
 if(input.media.length!==5||input.seasons.length!==26||[...input.media,...input.seasons].some(x=>!Number.isSafeInteger(x)||x<1))throw Error('scope');
 db=await new Promise((resolve,reject)=>{const d=new sqlite3.Database('/app/config/db/db.sqlite3',sqlite3.OPEN_READONLY,e=>e?reject(e):resolve(d));});
 await exec('PRAGMA query_only=ON; BEGIN');
 const changed=await all('SELECT id,seasonNumber,status,mediaId FROM season WHERE id IN ('+input.seasons.join(',')+') ORDER BY id');
 if(changed.length!==26)throw Error('missing-original-season');
 const mids=[...new Set([...input.media,...changed.map(s=>s.mediaId)])].sort((a,b)=>a-b);
 const media=await all('SELECT id,mediaType,status,tmdbId,tvdbId,serviceId,externalServiceId,ratingKey FROM media WHERE id IN ('+mids.join(',')+') ORDER BY id');
 const seasons=await all('SELECT id,seasonNumber,status,mediaId FROM season WHERE mediaId IN ('+mids.join(',')+') ORDER BY id');
 const token=(await all('SELECT plexToken FROM user WHERE id=1'))[0].plexToken;
 await exec('ROLLBACK');await new Promise(r=>db.close(r));db=undefined;
 const settings=readJSON('/app/config/settings.json');
 const headers={'X-Plex-Token':token,'X-Plex-Client-Identifier':settings.clientId};
 const report={media:[],seasons:[],historicalEventsObserved:false};
 for(const m of media){
  const row={mediaId:m.id,status:m.status,isChangedMedia:input.media.includes(m.id),type:m.mediaType,plex:null,sonarr:null};
  let plexSeasons=[];let sonarrSeasons=[];
  try{
   if(!m.ratingKey||!/^[0-9]+$/.test(m.ratingKey))throw Error('no-rating-key');
   const data=await getJSON(serviceURL(settings.plex.ip,settings.plex.port,settings.plex.useSsl,'','/library/metadata/'+m.ratingKey),headers);
   const item=data.MediaContainer?.Metadata?.[0];
   const children=await getJSON(serviceURL(settings.plex.ip,settings.plex.port,settings.plex.useSsl,'','/library/metadata/'+m.ratingKey+'/children'),headers);
   plexSeasons=children.MediaContainer?.Metadata||[];
   row.plex={present:!!item,ratingKeyMatches:item?.ratingKey===m.ratingKey,type:item?.type,leafCount:item?.leafCount,seasonCount:plexSeasons.length};
  }catch{row.plex={passed:false,reason:'exact-plex-metadata-read-unavailable'};}
  try{
   const config=settings.sonarr.find(s=>s.id===m.serviceId);
   if(!config||!Number.isSafeInteger(m.externalServiceId))throw Error('no-sonarr-link');
   const series=await getJSON(serviceURL(config.hostname,config.port,config.useSsl,config.baseUrl,'/api/v3/series/'+m.externalServiceId),{'X-Api-Key':config.apiKey});
   sonarrSeasons=series.seasons||[];
   row.sonarr={present:true,externalServiceIdMatches:series.id===m.externalServiceId,tvdbIdMatches:series.tvdbId===m.tvdbId,seasonCount:sonarrSeasons.length,statistics:series.statistics?{episodeFileCount:series.statistics.episodeFileCount,episodeCount:series.statistics.episodeCount,totalEpisodeCount:series.statistics.totalEpisodeCount}:null};
  }catch{row.sonarr={passed:false,reason:'exact-sonarr-series-read-unavailable'};}
  row.allRecordedNonSpecialSeasonsAvailable=seasons.filter(s=>s.mediaId===m.id&&s.seasonNumber!==0).every(s=>s.status===5);
  report.media.push(row);
  for(const s of changed.filter(s=>s.mediaId===m.id)){
   const plex=plexSeasons.find(p=>p.index===s.seasonNumber);const sonarr=sonarrSeasons.find(p=>p.seasonNumber===s.seasonNumber);const stats=sonarr?.statistics;
   report.seasons.push({seasonId:s.id,mediaId:m.id,seasonNumber:s.seasonNumber,status:s.status,plexPresent:!!plex,plexEpisodeCount:plex?.leafCount??null,sonarrPresent:!!sonarr,sonarrStats:stats?{episodeFileCount:stats.episodeFileCount,episodeCount:stats.episodeCount,totalEpisodeCount:stats.totalEpisodeCount,percentOfEpisodes:stats.percentOfEpisodes}:null});
  }
 }
 process.stdout.write(JSON.stringify(report));
})().catch(()=>{if(db)db.close();process.stdout.write(JSON.stringify({failed:true,category:'bounded-read-failed'}));process.exitCode=1;});
'''

def main():
    delta=OUT/'seerr-history-deltas-corrected.json'
    d=json.loads(delta.read_bytes())
    media=[r['id'] for r in d['tables']['media']['deltas'] if r['changes'].get('status')=={'old':4,'new':5}]
    seasons=[r['id'] for r in d['tables']['season']['deltas'] if r['changes'].get('status',{}).get('old')==7 and r['changes']['status']['new'] in [4,5]]
    assert len(media)==5 and len(seasons)==26
    identity=json.loads((OUT/'seerr-current.json').read_bytes())['identity']
    def fence():
        pod=json.loads(LIB['remote'](['kubectl','-n','plex','get','pod',identity['pod'],'-o','json']))
        assert pod['metadata']['uid']==identity['podUID'] and not pod['metadata'].get('deletionTimestamp')
        assert pod['spec']['containers'][0]['image']==identity['image']
        return pod['metadata']['uid'],pod['status']['containerStatuses'][0]['restartCount']
    before=fence()
    header=SOURCE.with_name('qualify-seerr.cjs').read_text().split('async function main()')[0]
    report=json.loads(LIB['remote'](['kubectl','-n','plex','exec','-i',identity['pod'],'-c','overseerr','--','node','-e',header+PAYLOAD],json.dumps({'media':media,'seasons':seasons}).encode()))
    assert before==fence()
    report.update(identity=identity,deltaReceiptSHA256=hashlib.sha256(delta.read_bytes()).hexdigest(),sourceSHA256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),literalComparisonPassed=False)
    target=OUT/'seerr-current-availability.json'
    with target.open('x') as f:json.dump(report,f,indent=2)
    target.chmod(0o600)
    print(json.dumps(report))

if __name__=='__main__':main()
