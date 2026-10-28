#!/usr/bin/env python3
"""Compare complete original rows and the exact documented vendor transformations."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path('/home/brajam/.local/share/branconet-migration/local-image-build-offload-20261025')
OUT = ROOT / 'upstream-mealie-20261026'
PROGRAM = r'''
import sqlite3,json,hashlib,importlib.util,collections,uuid
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from mealie.db.models._model_base import SqlAlchemyBase
from mealie.services.scraper.cleaner import clean_yield
from alembic.config import Config
from alembic.script import ScriptDirectory

base=Path('/opt/mealie/lib/python3.14/site-packages/mealie')
def load(pattern):
 paths=list((base/'alembic/versions').glob(pattern));assert len(paths)==1
 p=paths[0];spec=importlib.util.spec_from_file_location('time_migration',p);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
time=load('*27621d27c7e1*.py');words=time.load_unit_words();pattern=time.build_component_pattern(words)
def connect(path):
 c=sqlite3.connect('file:'+path+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;c.execute('PRAGMA query_only=ON');c.execute('BEGIN');assert c.execute('PRAGMA integrity_check').fetchall()[0][0]=='ok'and c.execute('PRAGMA foreign_key_check').fetchone()is None;return c
old=connect('/mnt/sqlite-original.db');new=connect('/app/data/mealie.db')
def names(c):return {r[0]for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
def quote(n):return '"'+n.replace('"','""')+'"'
def rows(c,t):return [dict(r)for r in c.execute('SELECT *FROM '+quote(t))]
def columns(c,t):return [r[1]for r in c.execute('PRAGMA table_xinfo('+quote(t)+')')]
def value(v):
 if isinstance(v,bytes):return ['bytes',v.hex()]
 return [type(v).__name__,v]
def project(c,t,cols):
 out=[]
 for r in rows(c,t):
  vals=[]
  for k in cols:
   v=r[k]
   if t=='recipes'and k=='rating'and v is not None:v=str(Decimal(str(v)).normalize())
   vals.append(value(v))
  out.append(json.dumps(vals,sort_keys=True,separators=(',',':')))
 return sorted(out)
legacy={'cookbooks_to_categories','cookbooks_to_tags','cookbooks_to_tools','plan_rules_to_categories','plan_rules_to_tags'}
excluded={'recipes':{'name_normalized','description_normalized','recipe_yield','prep_time','perform_time','total_time'},'recipes_ingredients':{'note_normalized','original_text_normalized','quantity'}}
ont,nnt=names(old),names(new);assert ont-nnt=={'users_to_favorites'}
checks={};common=0
for t in sorted(ont&nnt-legacy-{'alembic_version'}):
 cols=sorted(set(columns(old,t))&set(columns(new,t))-excluded.get(t,set()));assert project(old,t,cols)==project(new,t,cols), 'original-row-projection:'+t
 common+=1
checks['completeOriginalRowProjections']=common
assert not rows(old,'users_to_favorites')
heads=ScriptDirectory.from_config(Config(str(base/'alembic/alembic.ini'))).get_heads();assert [r['version_num']for r in rows(new,'alembic_version')]==heads
checks['declaredMigrationHead']=heads
oldrecipes={r['id']:r for r in rows(old,'recipes')};newrecipes={r['id']:r for r in rows(new,'recipes')};assert oldrecipes.keys()==newrecipes.keys()
for ident,r in oldrecipes.items():
 n=newrecipes[ident]
 for target,source in [('name_normalized','name'),('description_normalized','description')]:
  expected=SqlAlchemyBase.normalize(r[source])if r[source]is not None else None;assert n[target]==expected
 try:servings,quantity,label=clean_yield(r['recipe_yield'])
 except Exception:servings,quantity,label=0,0,r['recipe_yield']
 assert n['recipe_yield']==label and n['recipe_servings']==servings and n['recipe_yield_quantity']==quantity,'declared-yield-transform'
 for field in time.TIME_FIELDS:
  seconds=time.parse_seconds(r[field],words,pattern)
  if seconds is not None:assert n[field]is None and n[field+'_seconds']==seconds
  elif time.is_empty_time(r[field]):assert n[field]is None and n[field+'_seconds']is None
  else:assert n[field]==r[field]and n[field+'_seconds']is None
checks['allRecipeDerivedSearchYieldAndTimeFields']=len(oldrecipes)
settings={r['recipe_id']:r for r in rows(old,'recipe_settings')};ingredients={r['id']:r for r in rows(new,'recipes_ingredients')}
for r in rows(old,'recipes_ingredients'):
 n=ingredients[r['id']]
 for target,source in [('note_normalized','note'),('original_text_normalized','original_text')]:
  assert n[target]==(SqlAlchemyBase.normalize(r[source])if r[source]is not None else None)
 q=r['quantity'];q=0 if q==1 and settings[r['recipe_id']]['disable_amount']==1 else q
 assert(q is None and n['quantity']is None)or(q is not None and Decimal(str(q))==Decimal(str(n['quantity']))),'declared-amount-disabled-transform'
checks['allIngredientDerivedSearchAndQuantityFields']=len(ingredients)
oldusers={r['id']:r for r in rows(old,'users')};newusers={r['id']:r for r in rows(new,'users')};assert oldusers.keys()==newusers.keys()
households={r['group_id']:r for r in rows(new,'households')};assert set(households)=={r['id']for r in rows(old,'groups')}
for ident,r in oldusers.items():
 assert newusers[ident]['household_id']==households[r['group_id']]['id']and newusers[ident]['can_manage_household']==r['admin']
for t in ['cookbooks','group_events_notifiers','group_meal_plan_rules','invite_tokens','webhook_urls']:
 for r in rows(new,t):assert r['household_id']==households[r['group_id']]['id']
preferences={r['household_id']:r for r in rows(new,'household_preferences')}
defaults={'private_group':True,'first_day_of_week':0,'recipe_public':True,'recipe_show_nutrition':False,'recipe_show_assets':False,'recipe_landscape_view':False,'recipe_disable_comments':False,'recipe_disable_amount':True}
for r in rows(old,'group_preferences'):
 n=preferences[households[r['group_id']]['id']]
 for field,default in defaults.items():
  expected=r[field]if r[field]is not None else default;assert n['private_household'if field=='private_group'else field]==expected
checks['allOriginalUsersCredentialRowsAndHouseholdPermissions']=len(oldusers)
ratings=[]
for r in oldrecipes.values():
 if r['rating']is not None and r['rating']>0:
  for user in oldusers.values():
   if user['group_id']==r['group_id']:ratings.append((user['id'],r['id'],float(r['rating']),0))
actual=[(r['user_id'],r['recipe_id'],r['rating'],r['is_favorite'])for r in rows(new,'users_to_recipes')];assert sorted(actual)==sorted(ratings)
checks['allOriginalRatingsMappedToUsers']=len(ratings)
for t in legacy:assert not rows(new,t)
for r in rows(old,'cookbooks'):
 parts=[]
 for table,foreign,query,flag in [('cookbooks_to_categories','category_id','recipe_category.id','require_all_categories'),('cookbooks_to_tags','tag_id','tags.id','require_all_tags'),('cookbooks_to_tools','tool_id','tools.id','require_all_tools')]:
  links=[x[foreign]for x in rows(old,table)if x['cookbook_id']==r['id']]
  if links:
   rel='CONTAINS ALL'if r[flag]else'IN';vals=','.join('"'+str(uuid.UUID(x))+'"'for x in links);parts.append(query+' '+rel+' ['+vals+']')
 n=next(x for x in rows(new,'cookbooks')if x['id']==r['id']);assert n['query_filter_string']==' AND '.join(parts),'all-cookbook-filters'
assert not rows(old,'group_meal_plan_rules')
checks['allLegacyOrganizerRelationshipsPreservedInQueries']=sum(len(rows(old,t))for t in legacy)
expected=[]
for r in oldrecipes.values():
 if r['last_made']:expected.append((households[r['group_id']]['id'],r['id'],datetime.fromisoformat(r['last_made'])))
actual=[(r['household_id'],r['recipe_id'],datetime.fromisoformat(r['last_made']))for r in rows(new,'households_to_recipes')];assert sorted(actual)==sorted(expected)
checks['allLastMadeHistoryMappedToHouseholds']=len(expected)
assert not rows(old,'ingredient_foods')and not rows(old,'ingredient_units')and not rows(new,'ai_providers')
checks['unexpectedExistingUnitsFoodsOrAIProviders']=False
old.close();new.close();print(json.dumps({'passed':True,'productionChanged':False,'rawDataReturned':False,'checks':checks}))
'''


def main():
    assert sys.argv[1:] == ['--apply'] and os.getuid() == 1000
    cg = Path('/proc/self/cgroup').read_text().strip().removeprefix('0::')
    assert cg.endswith('/branconet-mealie-copy-audit-r2-20261026.service')
    group = Path('/sys/fs/cgroup') / cg.lstrip('/')
    assert (group / 'memory.max').read_text().strip() == str(1024**3) and (group / 'memory.swap.max').read_text().strip() == '0'
    assert not Path('/home/brajam/.ssh').exists() and not os.access('/mnt/c/Users', os.R_OK | os.X_OK)
    os.umask(0o077)
    assert OUT.resolve() == OUT and (OUT / 'vendor-rootfs/mnt').is_dir()
    assert not (OUT / 'copy-audit.json').exists()
    original = OUT / 'db-copy/sqlite-original.db'
    migrated = OUT / 'migration-data/mealie.db'
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [original, migrated]}
    cmd = ['/usr/bin/bwrap', '--unshare-all', '--new-session', '--die-with-parent', '--cap-drop', 'ALL',
           '--ro-bind', str(OUT / 'vendor-rootfs'), '/', '--proc', '/proc', '--dev', '/dev',
           '--ro-bind', str(OUT / 'db-copy'), '/mnt', '--bind', str(OUT / 'migration-data'), '/app/data',
           '--bind', str(OUT / 'migration-tmp'), '/tmp', '--chdir', '/app', '--clearenv',
           '--setenv', 'PATH', '/opt/mealie/bin:/usr/bin:/bin', '--setenv', 'HOME', '/tmp', '--setenv', 'TMPDIR', '/tmp',
           '--setenv', 'PRODUCTION', 'true', '--setenv', 'TESTING', 'false', '--setenv', 'DATA_DIR', '/app/data',
           '--', '/opt/mealie/bin/python', '-I', '-B', '-c', PROGRAM]
    with (OUT / 'copy-audit-r2.stderr').open('xb') as errors:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=errors, timeout=120)
    assert len(result.stdout) <= 1024**2
    with (OUT / 'copy-audit-r2.stdout').open('xb') as stream:
        stream.write(result.stdout)
    packets = [json.loads(line) for line in result.stdout.splitlines() if line.startswith(b'{"passed":')]
    assert result.returncode != 0 or len(packets) == 1
    report = packets[0] if result.returncode == 0 else {'passed': False, 'exit': result.returncode, 'rawDetailsSuppressed': True}
    after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [original, migrated]}
    assert before == after
    report.update(sourceSHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  originalAndMigratedDatabasesUnchanged=True, databaseSHA256=after,
                  productionChanged=False, networkDisabled=True)
    with (OUT / 'copy-audit.json').open('x') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps(report))
    return int(not report['passed'])


if __name__ == '__main__':
    raise SystemExit(main())
