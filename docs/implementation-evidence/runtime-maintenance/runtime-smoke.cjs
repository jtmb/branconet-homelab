
const fs=require('fs'),cp=require('child_process'),crypto=require('crypto'),path=require('path');
const {PrismaClient}=require('@prisma/client');
(async()=>{
  const legacy=process.env.QA_MIGRATION_MODE==='legacy-forward';
  const backend=process.env.QA_PROFILE==='backend';
  const env={...process.env,BOTRUS_JWT_SECRET:crypto.randomBytes(48).toString('hex'),BOTRUS_SECRETS_KEY:crypto.randomBytes(32).toString('hex'),BORTUS_SECRET_NAMESPACES:'apps,history',BORTUS_HISTORY_NAMESPACE:'history',BORTUS_KV_GUARDED_ADOPTION:'false'};
  const db=new PrismaClient();let child=null,output='';
  const writerHash=crypto.randomBytes(32).toString('hex'),readerHash=crypto.randomBytes(32).toString('hex');
  const quarantine=crypto.randomBytes(16).toString('hex');
  const stop=async()=>{const stopping=child;child=null;if(stopping&&stopping.exitCode===null&&stopping.signalCode===null){await new Promise(resolve=>{const timer=setTimeout(()=>{if(stopping.exitCode===null&&stopping.signalCode===null)stopping.kill('SIGKILL');resolve()},3000);timer.unref();stopping.once('exit',()=>{clearTimeout(timer);resolve()});stopping.kill('SIGTERM')})}};
  const boot=async()=>{
    output='';child=cp.spawn('./docker-entrypoint.sh',[],{env,stdio:['ignore','pipe','pipe']});
    child.stdout.on('data',x=>output=(output+x).slice(-65536));child.stderr.on('data',x=>output=(output+x).slice(-65536));
    let live=null,ready=null;
    for(let i=0;i<160;i++){if(child.exitCode!==null||child.signalCode!==null)break;try{live=(await fetch('http://127.0.0.1:4000/api/health/live',{signal:AbortSignal.timeout(1000)})).status;if(live===200)break}catch{}await new Promise(r=>setTimeout(r,250))}
    if(live===200)ready=(await fetch('http://127.0.0.1:4000/api/health/ready',{signal:AbortSignal.timeout(10000)})).status;
    return {live_status:live,ready_without_native_credentials:ready,migration_success_observed:output.includes('All migrations have been successfully applied')||output.includes('No pending migrations to apply')};
  };
  try {
    if(legacy){
      const dir='/tmp/bortus-synthetic-legacy';fs.mkdirSync(dir,{mode:0o700});fs.mkdirSync(dir+'/migrations');
      const current=fs.readFileSync('prisma/schema.prisma','utf8');
      const old=current.replace(/^  engineAdmin.*\r?\n/m,'').replace(/\/\/ KV tables contain metadata only\.[\s\S]*?(?=model Node)/,'');
      fs.writeFileSync(dir+'/schema.prisma',old,{mode:0o600});
      for(const name of fs.readdirSync('prisma/migrations'))if(name==='migration_lock.toml'||name<'20261010210000_kv_metadata')fs.cpSync('prisma/migrations/'+name,dir+'/migrations/'+name,{recursive:true});
      cp.execFileSync(process.execPath,['node_modules/prisma/build/index.js','migrate','deploy','--schema',dir+'/schema.prisma'],{env,stdio:'pipe'});
      await db.$executeRaw`INSERT INTO users (id,username,passwordHash,role,sessionVersion,createdAt) VALUES ('old-writer','fixture_writer',${writerHash},'write',7,'2026-10-01T00:00:00Z'),('old-reader','fixture_reader',${readerHash},'readonly',3,'2026-10-01T00:00:00Z')`;
      await db.secretReference.create({data:{alias:'fixture_original_under_scored',namespace:'apps',name:'fixture-native-reference',key:'under_scored_key'}});
      await db.variable.create({data:{key:'fixture_quarantined_legacy',value:quarantine,encrypted:true,category:'secret'}});
      if(backend){
        // Seed the nine-migration metadata checkpoint, then let the image entrypoint
        // apply the two additive migrations. Every stored item is synthetic metadata.
        fs.cpSync('prisma/migrations/20261010210000_kv_metadata',dir+'/migrations/20261010210000_kv_metadata',{recursive:true});
        fs.writeFileSync(dir+'/schema.prisma',current.replace(/^  consumerUid.*\r?\n/m,'').replace(/^  consumerResourceVersion.*\r?\n/m,''),{mode:0o600});
        cp.execFileSync(process.execPath,['node_modules/prisma/build/index.js','migrate','deploy','--schema',dir+'/schema.prisma'],{env,stdio:'pipe'});
        await db.kvMount.create({data:{id:'fixture-mount',name:'fixture-mount',namespaces:'["apps"]'}});
        await db.kvPath.create({data:{id:'fixture-path',mountId:'fixture-mount',path:'fixture/credential',namespace:'apps',name:'fixture-native-reference'}});
        await db.kvField.create({data:{id:'fixture-field',pathId:'fixture-path',field:'under_scored_key',namespace:'apps',name:'fixture-native-reference',key:'under_scored_key'}});
        await db.kvLegacyGrant.create({data:{id:'fixture-grant',pathId:'fixture-path',alias:'fixture_original_under_scored',namespace:'apps',name:'fixture-native-reference',key:'under_scored_key'}});
        await db.kvOperation.create({data:{id:'fixture-operation',actorId:'old-writer',pathId:'fixture-path',mountId:'fixture-mount',path:'fixture/credential',namespace:'apps',name:'fixture-native-reference',action:'read',outcome:'committed'}});
        await db.$executeRaw`INSERT INTO kv_rotations (id,pathId,actorId,field,consumerKind,consumerNamespace,consumerName,state,revision,createdAt,updatedAt) VALUES ('fixture-rotation','fixture-path','old-writer','under_scored_key','Deployment','apps','fixture-consumer','prepare',1,'2026-10-01T00:00:00Z','2026-10-01T00:00:00Z')`;
        await db.$executeRaw`INSERT INTO kv_audit (id,actorId,action,pathId,outcome,createdAt) VALUES ('fixture-audit','old-writer','read','fixture-path','authorized','2026-10-01T00:00:00Z')`;
      }
    }
    const first=await boot();
    const tables={};for(const model of ['kvMount','kvPath','kvField','kvPolicy','kvIdentity','kvServicePrincipal','kvLegacyGrant','kvOperation','kvAudit','kvRotation'])tables[model]=await db[model].count();
    const lock=await db.accountLock.findUnique({where:{id:1}}),principal=await db.kvServicePrincipal.findUnique({where:{id:'legacy-lookup'}});
    const migrations=await db.$queryRawUnsafe('SELECT COUNT(*) AS count FROM _prisma_migrations WHERE finished_at IS NOT NULL AND rolled_back_at IS NULL');
    const expectedMigrationCount=fs.readdirSync('prisma/migrations').filter(n=>fs.statSync('prisma/migrations/'+n).isDirectory()).length;
    let preserved=true,migratedRoles=true,policies=true;
    if(legacy){
      const writer=await db.user.findUniqueOrThrow({where:{id:'old-writer'}}),reader=await db.user.findUniqueOrThrow({where:{id:'old-reader'}});
      const alias=await db.secretReference.findUniqueOrThrow({where:{alias:'fixture_original_under_scored'}}),variable=await db.variable.findUniqueOrThrow({where:{key:'fixture_quarantined_legacy'}});
      preserved=writer.passwordHash===writerHash&&writer.username==='fixture_writer'&&writer.role==='write'&&writer.sessionVersion===7&&reader.passwordHash===readerHash&&reader.role==='readonly'&&reader.sessionVersion===3&&alias.namespace==='apps'&&alias.name==='fixture-native-reference'&&alias.key==='under_scored_key'&&variable.value===quarantine;
      migratedRoles=writer.engineAdmin===true&&reader.engineAdmin===false;
      const grants=await db.kvPolicy.findMany();policies=grants.some(p=>p.principal==='user:old-writer'&&JSON.parse(p.actions).includes('destroy'))&&grants.some(p=>p.principal==='user:old-reader'&&JSON.stringify(JSON.parse(p.actions))==='["list"]');
    }
    const metadataPreserved=async()=>{
      if(!legacy||!backend)return true;
      const rotation=await db.kvRotation.findUniqueOrThrow({where:{id:'fixture-rotation'}}),audit=await db.kvAudit.findUniqueOrThrow({where:{id:'fixture-audit'}});
      const grant=await db.kvLegacyGrant.findUniqueOrThrow({where:{id:'fixture-grant'}}),op=await db.kvOperation.findUniqueOrThrow({where:{id:'fixture-operation'}});
      const registered=await db.kvPath.findUniqueOrThrow({where:{id:'fixture-path'}}),field=await db.kvField.findUniqueOrThrow({where:{id:'fixture-field'}}),mount=await db.kvMount.findUniqueOrThrow({where:{id:'fixture-mount'}});
      return rotation.pathId==='fixture-path'&&rotation.actorId==='old-writer'&&rotation.field==='under_scored_key'&&rotation.state==='prepare'&&rotation.revision===1&&rotation.consumerUid===null&&rotation.consumerResourceVersion===null&&audit.actorId==='old-writer'&&audit.action==='read'&&audit.outcome==='authorized'&&audit.principal===null&&audit.alias===null&&audit.key===null&&grant.alias==='fixture_original_under_scored'&&grant.key==='under_scored_key'&&op.outcome==='committed'&&registered.mountId===mount.id&&registered.name==='fixture-native-reference'&&field.key==='under_scored_key';
    };
    const emptyOwnership=['kvMount','kvPath','kvField','kvIdentity','kvLegacyGrant','kvOperation','kvAudit','kvRotation'].every(m=>tables[m]===(legacy&&backend&&m!=='kvIdentity'?1:0));
    const metadataBeforeRestart=await metadataPreserved();
    const diff=cp.execFileSync(process.execPath,['node_modules/prisma/build/index.js','migrate','diff','--from-url',process.env.DATABASE_URL,'--to-schema-datamodel','prisma/schema.prisma','--script'],{env,encoding:'utf8',stdio:['ignore','pipe','pipe']});
    const zeroSchemaDrift=diff.includes('empty migration');
    await stop();const second=await boot();
    let restartPreserved=true;
    if(legacy){const writer=await db.user.findUniqueOrThrow({where:{id:'old-writer'}});restartPreserved=writer.passwordHash===writerHash&&writer.sessionVersion===7&&writer.engineAdmin===true&&(await db.secretReference.count())===1;}
    const metadataAfterRestart=await metadataPreserved();
    const result={migration_mode:legacy?'legacy-forward':'fresh',node:process.versions.node,platform:process.platform,arch:process.arch,uid:process.getuid(),gid:process.getgid(),database_created:fs.existsSync('/data/bortus.db'),first_boot:first,second_boot:second,applied_migration_count:Number(migrations[0].count),expected_migration_count:expectedMigrationCount,kv_metadata_tables:tables,migration_lock_and_legacy_principal_present:Boolean(lock&&principal),synthetic_legacy_accounts_aliases_and_quarantined_value_preserved:legacy?preserved:null,existing_writer_admin_reader_nonadmin:legacy?migratedRoles:null,existing_user_policy_bridge_present:legacy?policies:null,ownership_history_audit_not_ingested_from_legacy_sqlite:emptyOwnership,synthetic_existing_metadata_and_nullable_additive_columns_preserved:legacy&&backend?metadataBeforeRestart&&metadataAfterRestart:null,zero_schema_drift:zeroSchemaDrift,restart_preservation_verified:restartPreserved,native_credentials_or_production_database_mounted:false,fixture_signing_material_values_or_hashes_recorded:false};
    result.passed=[first,second].every(b=>b.live_status===200&&b.ready_without_native_credentials===503&&b.migration_success_observed)&&result.database_created&&result.applied_migration_count===expectedMigrationCount&&expectedMigrationCount===(backend?11:9)&&Boolean(lock&&principal)&&emptyOwnership&&metadataBeforeRestart&&metadataAfterRestart&&zeroSchemaDrift&&preserved&&migratedRoles&&policies&&restartPreserved&&result.node==='22.23.3'&&result.uid===1000&&result.gid===1000;
    console.log(JSON.stringify(result));if(!result.passed)process.exitCode=1;
  } finally {await stop();await db.$disconnect()}
})().catch(()=>{console.error('Disposable KV runtime migration check failed; response/values withheld');process.exitCode=1});
