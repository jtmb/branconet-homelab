#include "node_api.h"

/* Prototype-only flat projection: complete bounded byte validation, native
 * selected summary objects, no ignored/native value strings or DOM. */
#define MAX_CHUNKS 16384
#define MAX_BYTES (4u * 1024u * 1024u)
typedef unsigned int U;
typedef struct { const unsigned char *p; size_t n; U begin; } Part;
typedef struct { U begin, end; int ascii, cross; } Span;
typedef struct { char bytes[16]; U n; int unknown; } Name;
typedef struct {
  napi_env env; napi_value namespaceValue, output, current, keys, version, kind, itemVersion, itemKind, cursor, type;
  napi_value ns, name, rv;
  int haveMeta, uidValid, rvValid, immutable;
  U emitted, createdStrings, decodedUnits, indexLookups, indexComparisons;
  Part *parts; U count, at, offset, pos, limit, items, skippedProperties;
  int failed, beginPending;
} Parser;

enum { ROOT_API=1, ROOT_KIND, ROOT_META, ITEM_BEGIN, ITEM_API,
       ITEM_KIND, ITEM_META, ITEM_TYPE, ITEM_IMMUTABLE, DATA_KEY,
       STRINGDATA_KEY, ITEM_END, PROPERTY_KEY };

static int peek(Parser *p) {
  while (p->at < p->count && p->offset == p->parts[p->at].n) {
    ++p->at; p->offset=0;
  }
  return p->at < p->count ? p->parts[p->at].p[p->offset] : -1;
}
static int take(Parser *p) {
  int b=peek(p); if (b>=0) { ++p->offset; ++p->pos; } return b;
}
static int expect(Parser *p,int b) { return take(p)==b; }
static void space(Parser *p) {
  for (;;) { int b=peek(p); if(b!=32 && b!=9 && b!=10 && b!=13) return; take(p); }
}
static int digit(int b) { return b>=48 && b<=57; }
static int hex(int b) {
  if (b>=48 && b<=57) return b-48;
  if (b>=65 && b<=70) return b-55;
  if (b>=97 && b<=102) return b-87;
  return -1;
}
static void namebyte(Name *n,U b) {
  if (!n) return;
  if (b>127) n->unknown=1;
  if(n->n<16) n->bytes[n->n]=(char)b;
  ++n->n;
}
static int emit(Parser *p,U kind,Span s);
static int event(Parser *p,U kind) { Span s={p->pos,p->pos,0,0}; return emit(p,kind,s); }
static int string(Parser *p,Span *span,Name *name) {
  U begin=p->pos; int ascii=1;
  if (!expect(p,34)) return 0;
  U firstChunk=p->at;
  if(name) {name->n=0;name->unknown=0;}
  for (;;) {
    if(peek(p)<0) return 0;
    const Part *part=&p->parts[p->at]; U start=p->offset;
    while(p->offset<part->n) {
      unsigned char b=part->p[p->offset];
      if(b<32 || b>=128 || b==34 || b==92) break;
      namebyte(name,b); ++p->offset;
    }
    p->pos+=p->offset-start;
    if(p->offset==part->n) continue;
    int b=take(p);
    if(b==34) {
      if(span) {span->begin=begin;span->end=p->pos;span->ascii=ascii;span->cross=firstChunk!=p->at;}
      return 1;
    }
    if(b==92) {
      ascii=0; int e=take(p);
      if(e==117) {
        U value=0;
        for(int i=0;i<4;++i) {int h=hex(take(p));if(h<0)return 0;value=(value<<4)|(U)h;}
        /* Match current JS: escaped lone surrogates are valid JSON escapes.
         * Raw UTF8-encoded surrogate codepoints are rejected below. */
        namebyte(name,value);
      } else {
        int decoded;
        if(e==34 || e==92 || e==47) decoded=e;
        else if(e==98) decoded=8; else if(e==102) decoded=12;
        else if(e==110) decoded=10; else if(e==114) decoded=13;
        else if(e==116) decoded=9; else return 0;
        namebyte(name,(U)decoded);
      }
    } else if(b>=128) {
      ascii=0; if(name)name->unknown=1;
      int n=b>=194&&b<=223?1:b>=224&&b<=239?2:b>=240&&b<=244?3:-1;
      if(n<0)return 0;
      for(int i=0;i<n;++i) {
        int next=take(p);
        if(next<128 || next>191 || (i==0 &&
          ((b==224&&next<160)||(b==237&&next>159)||
           (b==240&&next<144)||(b==244&&next>143))))return 0;
      }
    } else return 0;
  }
}
static int equals(const Name *n,const char *known,U count) {
  if(n->unknown || n->n!=count)return 0;
  for(U i=0;i<count;++i)if(n->bytes[i]!=known[i])return 0;
  return 1;
}
static U field(const Name *n,int root) {
  if(equals(n,"apiVersion",10))return 1;
  if(equals(n,"kind",4))return 2;
  if(equals(n,"metadata",8))return 4;
  if(root)return equals(n,"items",5)?8:0;
  if(equals(n,"data",4))return 8;
  if(equals(n,"stringData",10))return 16;
  if(equals(n,"type",4))return 32;
  if(equals(n,"immutable",9))return 64;
  return 0;
}
static int literal(Parser *p,const char *text,U n) {
  for(U i=0;i<n;++i)if(!expect(p,(unsigned char)text[i]))return 0;
  return 1;
}
static int skip(Parser *p,U depth) {
  if(depth>32)return 0;
  space(p);int b=peek(p);
  if(b==34)return string(p,0,0);
  if(b==123 || b==91) {
    int object=b==123,end=object?125:93;take(p);space(p);
    if(peek(p)==end){take(p);return 1;}
    for(;;) {
      if(object) {if(!string(p,0,0))return 0;space(p);if(!expect(p,58))return 0;}
      if(!skip(p,depth+1))return 0;space(p);b=take(p);
      if(b==end)return 1;if(b!=44)return 0;space(p);
    }
  }
  if(b==116)return literal(p,"true",4);
  if(b==102)return literal(p,"false",5);
  if(b==110)return literal(p,"null",4);
  if(b==45){take(p);b=peek(p);}
  if(b==48)take(p);
  else if(b>=49&&b<=57){do{take(p);}while(digit(peek(p)));}
  else return 0;
  if(peek(p)==46){take(p);if(!digit(peek(p)))return 0;do{take(p);}while(digit(peek(p)));}
  if(peek(p)==101 || peek(p)==69) {
    take(p);if(peek(p)==43||peek(p)==45)take(p);
    if(!digit(peek(p)))return 0;do{take(p);}while(digit(peek(p)));
  }
  return 1;
}

static Parser view(Parser *p,U position) {
  Parser q=*p;U lo=0,hi=p->count;++p->indexLookups;
  /* Upper-bound prefix search chooses the last equal prefix, correctly passing
   * empty chunks. At most15 comparisons for the fixed16384 chunk ceiling. */
  while(lo<hi){U middle=lo+(hi-lo)/2;++p->indexComparisons;
    if(p->parts[middle].begin<=position)lo=middle+1;else hi=middle;
  }
  q.at=lo?lo-1:0;q.offset=lo?position-p->parts[q.at].begin:0;q.pos=position;
  return q;
}
/* Decode only selected string spans; skipped native/unknown values never enter
 * this function. Grammar and fatal raw UTF8 validation have already completed. */
static int text(Parser *p,Span s,napi_value *value) {
  Parser q=view(p,s.begin);if(!expect(&q,34))return 0;
  if(s.ascii && !s.cross) {
    const Part *part=&q.parts[q.at];U n=s.end-s.begin-2;
    if(q.offset+n>part->n)return 0;
    ++p->createdStrings;p->decodedUnits+=n;
    return napi_create_string_utf8(p->env,(const char *)part->p+q.offset,n,value)==napi_ok;
  }
  napi_value scratch;void *memory;size_t units=0;
  if(napi_create_arraybuffer(p->env,2u*(s.end-s.begin),&memory,&scratch)!=napi_ok)return 0;
  uint16_t *out=memory;
  while(q.pos<s.end-1) {
    int b=take(&q);U cp=(U)b;
    if(b==92) {
      int e=take(&q);
      if(e==117){cp=0;for(int i=0;i<4;++i){int h=hex(take(&q));if(h<0)return 0;cp=(cp<<4)|(U)h;}}
      else if(e==34||e==92||e==47)cp=(U)e;
      else if(e==98)cp=8;else if(e==102)cp=12;else if(e==110)cp=10;else if(e==114)cp=13;else if(e==116)cp=9;else return 0;
    } else if(b>=128) {
      int n=b<=223?1:b<=239?2:3;cp=(U)b&((1u<<(6-n))-1u);
      for(int i=0;i<n;++i)cp=(cp<<6)|((U)take(&q)&63u);
      if(cp>65535){cp-=65536;out[units++]=(uint16_t)(55296+(cp>>10));cp=56320+(cp&1023);}
    }
    out[units++]=(uint16_t)cp;
  }
  if(!expect(&q,34)||q.pos!=s.end)return 0;
  ++p->createdStrings;p->decodedUnits+=(U)units;
  return napi_create_string_utf16(p->env,out,units,value)==napi_ok;
}
static int word(Parser *p,napi_value value,const char *expected,U n) {
  size_t length;char bytes[32];
  if(napi_get_value_string_utf8(p->env,value,0,0,&length)!=napi_ok||length!=n||n>=sizeof(bytes))return 0;
  if(napi_get_value_string_utf8(p->env,value,bytes,sizeof(bytes),&length)!=napi_ok)return 0;
  for(U i=0;i<n;++i)if(bytes[i]!=expected[i])return 0;return 1;
}
static int dns(Parser *p,napi_value value,U maximum,int dots) {
  size_t length;char bytes[254];
  if(napi_get_value_string_utf8(p->env,value,0,0,&length)!=napi_ok||length<1||length>maximum)return 0;
  if(napi_get_value_string_utf8(p->env,value,bytes,sizeof(bytes),&length)!=napi_ok)return 0;
  U component=0;int previous=0;
  for(U i=0;i<length;++i){int b=(unsigned char)bytes[i];int alpha=(b>=97&&b<=122)||(b>=48&&b<=57);
    if(b==46&&dots){if(component<1||component>63||previous==45)return 0;component=0;}
    else {if(!alpha&&b!=45)return 0;if(!component&&b==45)return 0;++component;}
    previous=b;
  }
  return component>0&&component<=63&&previous!=45;
}
static int put(Parser *p,napi_value object,const char *key,napi_value value){
  napi_property_descriptor d={0};d.utf8name=key;d.value=value;d.attributes=napi_writable|napi_enumerable|napi_configurable;
  return napi_define_properties(p->env,object,1,&d)==napi_ok;
}
static int projection(Parser *p,Span span,int root) {
  Parser q=view(p,span.begin);if(!expect(&q,123))return 0;space(&q);
  if(!root){p->haveMeta=1;p->uidValid=p->rvValid=1;if(napi_get_undefined(p->env,&p->ns)!=napi_ok||napi_get_undefined(p->env,&p->name)!=napi_ok||napi_get_undefined(p->env,&p->rv)!=napi_ok)return 0;}
  else if(napi_create_string_utf8(p->env,"",0,&p->cursor)!=napi_ok)return 0;
  if(peek(&q)==125){take(&q);return q.pos==span.end;}
  for(;;){Name fieldName;Span key;if(!string(&q,&key,&fieldName))return 0;space(&q);if(!expect(&q,58))return 0;space(&q);
    U selected=root?(equals(&fieldName,"continue",8)?1:0):equals(&fieldName,"namespace",9)?1:equals(&fieldName,"name",4)?2:equals(&fieldName,"resourceVersion",15)?3:equals(&fieldName,"uid",3)?4:0;
    if(selected){
      napi_value v;int valid=peek(&q)==34;
      if(valid){Span s;if(!string(&q,&s,0))return 0;
        if(!root&&selected==4){p->uidValid=1;}
        else {if(!text(p,s,&v))return 0;if(root)p->cursor=v;else if(selected==1)p->ns=v;else if(selected==2)p->name=v;else {p->rv=v;p->rvValid=1;}}
      } else {if(!skip(&q,root?2:3))return 0;
        if(root){if(napi_get_undefined(p->env,&p->cursor)!=napi_ok)return 0;}
        else if(selected==4)p->uidValid=0;else if(selected==3)p->rvValid=0;
        else {if(napi_get_undefined(p->env,&v)!=napi_ok)return 0;if(selected==1)p->ns=v;else p->name=v;}
      }
    }else if(!skip(&q,root?2:3))return 0;
    space(&q);int b=take(&q);if(b==125)return q.pos==span.end;if(b!=44)return 0;space(&q);
  }
}
static int emit(Parser *p,U kind,Span s) {
  ++p->emitted;napi_value value;
  if(kind==PROPERTY_KEY||kind==STRINGDATA_KEY)return 1;
  if(kind==ITEM_BEGIN){
    p->haveMeta=0;p->immutable=0;p->uidValid=p->rvValid=1;
    return napi_create_object(p->env,&p->current)==napi_ok&&napi_create_object(p->env,&p->keys)==napi_ok&&
      napi_create_string_utf8(p->env,"Opaque",6,&p->type)==napi_ok&&
      napi_get_undefined(p->env,&p->itemVersion)==napi_ok&&napi_get_undefined(p->env,&p->itemKind)==napi_ok;
  }
  if(kind==ROOT_META||kind==ITEM_META)return projection(p,s,kind==ROOT_META);
  if(kind==ITEM_IMMUTABLE){Parser q=view(p,s.begin);p->immutable=peek(&q)==116;return 1;}
  if(kind==ITEM_END){bool same=false;napi_value array,method,sorted,immutable;
    if(!p->haveMeta||!p->uidValid||!p->rvValid||!word(p,p->itemVersion,"v1",2)||!word(p,p->itemKind,"Secret",6)||
       napi_strict_equals(p->env,p->ns,p->namespaceValue,&same)!=napi_ok||!same||!dns(p,p->namespaceValue,63,0)||!dns(p,p->name,253,1))return 0;
    if(napi_get_all_property_names(p->env,p->keys,napi_key_own_only,napi_key_all_properties,napi_key_numbers_to_strings,&array)!=napi_ok||
       napi_get_named_property(p->env,array,"sort",&method)!=napi_ok||napi_call_function(p->env,array,method,0,0,&sorted)!=napi_ok||
       napi_get_boolean(p->env,p->immutable,&immutable)!=napi_ok)return 0;
    return put(p,p->current,"namespace",p->ns)&&put(p,p->current,"name",p->name)&&put(p,p->current,"resourceVersion",p->rv)&&
      put(p,p->current,"type",p->type)&&put(p,p->current,"immutable",immutable)&&put(p,p->current,"keys",array)&&
      napi_set_element(p->env,p->output,p->items-1,p->current)==napi_ok;
  }
  if(!text(p,s,&value))return 0;
  if(kind==ROOT_API)p->version=value;else if(kind==ROOT_KIND)p->kind=value;
  else if(kind==ITEM_API)p->itemVersion=value;else if(kind==ITEM_KIND)p->itemKind=value;
  else if(kind==ITEM_TYPE){size_t length;if(napi_get_value_string_utf16(p->env,value,0,0,&length)!=napi_ok)return 0;if(length)p->type=value;}
  else if(kind==DATA_KEY){napi_value one;if(napi_get_boolean(p->env,1,&one)!=napi_ok)return 0;
    napi_property_descriptor d={0};d.name=value;d.value=one;d.attributes=napi_writable|napi_enumerable|napi_configurable;
    if(napi_define_properties(p->env,p->keys,1,&d)!=napi_ok)return 0;
  }else return 0;return 1;
}
static int selected_text(Parser *p,U event_kind) {
  Span s;if(!string(p,&s,0))return 0;return emit(p,event_kind,s);
}
static int selected_meta(Parser *p,U depth,U event_kind) {
  Span s;s.begin=p->pos;s.ascii=0;
  if(peek(p)!=123 || !skip(p,depth))return 0;
  s.end=p->pos;return emit(p,event_kind,s);
}
static int data(Parser *p,U key_event) {
  if(!expect(p,123))return 0;space(p);
  if(peek(p)==125){take(p);return 1;}
  for(;;) {
    Span s;if(!string(p,&s,0) || !emit(p,key_event,s))return 0;
    space(p);if(!expect(p,58))return 0;space(p);
    if(!string(p,0,0))return 0;space(p);int b=take(p);
    if(b==125)return 1;if(b!=44)return 0;space(p);
  }
}
static int item(Parser *p) {
  if(!event(p,ITEM_BEGIN) || !expect(p,123))return 0;
  space(p);U fields=0;
  if(peek(p)==125){take(p);return event(p,ITEM_END);}
  for(;;) {
    Name name;Span key;
    if(!string(p,&key,&name))return 0;
    if(key.ascii && !key.cross) ++p->skippedProperties;
    else if(!emit(p,PROPERTY_KEY,key))return 0;
    space(p);if(!expect(p,58))return 0;space(p);
    U bit=field(&name,0);if(bit){if(fields&bit)return 0;fields|=bit;}
    if(bit==1){if(!selected_text(p,ITEM_API))return 0;}
    else if(bit==2){if(!selected_text(p,ITEM_KIND))return 0;}
    else if(bit==4){if(!selected_meta(p,2,ITEM_META))return 0;}
    else if(bit==8){if(!data(p,DATA_KEY))return 0;}
    else if(bit==16){if(!data(p,STRINGDATA_KEY))return 0;}
    else if(bit==32){if(!selected_text(p,ITEM_TYPE))return 0;}
    else if(bit==64) {
      Span s;s.begin=p->pos;s.ascii=0;
      int b=peek(p);if((b!=116&&b!=102)||!skip(p,2))return 0;
      s.end=p->pos;if(!emit(p,ITEM_IMMUTABLE,s))return 0;
    } else if(!skip(p,2))return 0;
    space(p);int b=take(p);if(b==125)return event(p,ITEM_END);
    if(b!=44)return 0;space(p);
  }
}
static int items(Parser *p) {
  if(!expect(p,91))return 0;space(p);
  if(peek(p)==93){take(p);return 1;}
  for(;;) {
    if(p->items>=p->limit)return 0;++p->items;
    if(!item(p))return 0;space(p);int b=take(p);
    if(b==93)return 1;if(b!=44)return 0;space(p);
  }
}
static int document(Parser *p) {
  space(p);if(!expect(p,123))return 0;space(p);U fields=0;
  if(peek(p)==125)return 0;
  for(;;) {
    Name name;Span key;
    if(!string(p,&key,&name))return 0;
    if(key.ascii && !key.cross) ++p->skippedProperties;
    else if(!emit(p,PROPERTY_KEY,key))return 0;
    space(p);if(!expect(p,58))return 0;space(p);
    U bit=field(&name,1);if(bit){if(fields&bit)return 0;fields|=bit;}
    if(bit==1){if(!selected_text(p,ROOT_API))return 0;}
    else if(bit==2){if(!selected_text(p,ROOT_KIND))return 0;}
    else if(bit==4){if(!selected_meta(p,1,ROOT_META))return 0;}
    else if(bit==8){if(!items(p))return 0;}
    else if(!skip(p,1))return 0;
    space(p);int b=take(p);if(b==125)break;if(b!=44)return 0;space(p);
  }
  space(p);return peek(p)==-1 && (fields&8);
}
static napi_value invalid(napi_env env) {
  bool pending=false;napi_is_exception_pending(env,&pending);
  if(pending){napi_value ignored;napi_get_and_clear_last_exception(env,&ignored);}
  napi_throw_error(env,"SUMMARY_INVALID","Invalid Kubernetes Secret summary response");
  return 0;
}
static napi_value scan(napi_env env,napi_callback_info info) {
  size_t argc=3;napi_value argv[3];void *measure=0;
  if(napi_get_cb_info(env,info,&argc,argv,0,&measure)!=napi_ok || argc!=3)return invalid(env);
  bool array=false;if(napi_is_array(env,argv[0],&array)!=napi_ok || !array)return invalid(env);
  U count;if(napi_get_array_length(env,argv[0],&count)!=napi_ok || count>MAX_CHUNKS)return invalid(env);
  double limit;if(napi_get_value_double(env,argv[1],&limit)!=napi_ok || !(limit>=1&&limit<=200) || (double)(U)limit!=limit)return invalid(env);
  
  Part parts[MAX_CHUNKS];U total=0;
  for(U i=0;i<count;++i) {
    napi_value value;bool buffer=false;void *raw;size_t length;
    if(napi_get_element(env,argv[0],i,&value)!=napi_ok || napi_is_buffer(env,value,&buffer)!=napi_ok || !buffer || napi_get_buffer_info(env,value,&raw,&length)!=napi_ok || length>MAX_BYTES-total)return invalid(env);
    parts[i].p=raw;parts[i].n=length;parts[i].begin=total;total+=(U)length;
  }
  Parser p;p.env=env;p.namespaceValue=argv[2];p.parts=parts;p.count=count;p.at=0;p.offset=0;p.pos=0;p.limit=(U)limit;p.items=0;p.failed=0;p.skippedProperties=0;p.beginPending=0;p.emitted=0;p.createdStrings=0;p.decodedUnits=0;p.indexLookups=0;p.indexComparisons=0;
  if(napi_create_array(env,&p.output)!=napi_ok||napi_get_undefined(env,&p.version)!=napi_ok||napi_get_undefined(env,&p.kind)!=napi_ok||napi_create_string_utf8(env,"",0,&p.cursor)!=napi_ok)return invalid(env);
  if(!document(&p)||!word(&p,p.version,"v1",2)||!word(&p,p.kind,"SecretList",10))return invalid(env);
  size_t cursorLength;if(napi_get_value_string_utf16(env,p.cursor,0,0,&cursorLength)!=napi_ok||cursorLength>8192)return invalid(env);
  napi_value result;if(napi_create_object(env,&result)!=napi_ok||!put(&p,result,"items",p.output)||!put(&p,result,"cursor",p.cursor))return invalid(env);
  if(measure){napi_value stats,wrapper,n;if(napi_create_object(env,&stats)!=napi_ok||napi_create_object(env,&wrapper)!=napi_ok)return invalid(env);
    if(napi_create_uint32(env,p.indexLookups,&n)!=napi_ok||!put(&p,stats,"indexLookups",n))return invalid(env);
    if(napi_create_uint32(env,p.indexComparisons,&n)!=napi_ok||!put(&p,stats,"indexComparisons",n))return invalid(env);
    if(napi_create_uint32(env,p.createdStrings,&n)!=napi_ok||!put(&p,stats,"createdStrings",n))return invalid(env);
    if(napi_create_uint32(env,p.decodedUnits,&n)!=napi_ok||!put(&p,stats,"decodedUnits",n))return invalid(env);
    if(!put(&p,wrapper,"page",result)||!put(&p,wrapper,"stats",stats))return invalid(env);return wrapper;
  }
  return result;
}
static napi_value init(napi_env env,napi_value exports) {
  napi_value method;napi_property_descriptor d={0};d.attributes=napi_writable|napi_enumerable|napi_configurable;
  if(napi_create_function(env,"flat",4,scan,0,&method)!=napi_ok)return invalid(env);d.utf8name="flat";d.value=method;if(napi_define_properties(env,exports,1,&d)!=napi_ok)return invalid(env);
  if(napi_create_function(env,"flatMeasured",12,scan,(void *)1,&method)!=napi_ok)return invalid(env);d.utf8name="flatMeasured";d.value=method;if(napi_define_properties(env,exports,1,&d)!=napi_ok)return invalid(env);return exports;
}
NAPI_MODULE(NODE_GYP_MODULE_NAME,init)
