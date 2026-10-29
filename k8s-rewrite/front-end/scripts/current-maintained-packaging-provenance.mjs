// Maintained exact current PUBLIC pins with raw-reader checks; original helper and all five function bodies preserved.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

// Two complete reviewed source lineages; mixed or unknown packaging refuses.
// Historical functional inputs keep their literal hashes in each caller.
const localPins = Object.freeze({
  ".dockerignore": "3e50275b9640a6f0ddd40e9b99c44b7af1fe0b136b2ff225f4d5c6956663fb28",
  "Dockerfile": "1aeb71c5b94b51dfffcb5593609194c010bfe353797389291f92076c546550ff",
  "Dockerfile.release": "ce4212677872de2dc354146d4f0a86ca43dac9503d6c2b6d6ca354bb08e6ce98",
  "src/app/(dashboard)/sidebar.tsx": "d219a5eb7e4ec36bc98c370ede03caff3bed7596d4e1eaa1b1d68859cbb2c5bc"
});
const publicPins = Object.freeze({
  ".dockerignore": "91bcd3d5dd7ae0043d81c43fdd4f8a5fde08f424712752288ed32f626940a9ba",
  "Dockerfile": "3533ac8664f7be99ab545760a4e764a405cdc80b267afb436f90359387c8643f",
  "Dockerfile.release": "9b936390a62c06a72138a3a42046cd68c4611fa669fc771bf24ea052df27a29b",
  "src/app/(dashboard)/sidebar.tsx": "5afdb24bcc80b8bf468287b4aade8e082a2b8dbc1f21cea7603b771de56e072e"
});
const digest = bytes => { assert.ok(Buffer.isBuffer(bytes), 'Raw Buffer reader required'); return createHash('sha256').update(bytes).digest('hex'); };

export function packagingLineage(importer, reader = readFileSync) {
  const observed = Object.fromEntries(Object.keys(localPins).map(name =>
    [name, digest(reader(new URL('../' + name, importer)))]));
  const matches = [['local', localPins], ['public', publicPins]].filter(([, pins]) =>
    Object.keys(pins).every(name => observed[name] === pins[name]));
  assert.equal(matches.length, 1, 'Unknown or mixed packaging source lineage');
  return matches[0][0];
}

const implementationPins = Object.freeze({
  "src/app/api/kv/legacy/preview/route.ts": {
    "historical": "fd60bd538707406140a8fc4e3c7189b2a9ba27880a3501491897dc2c68ef714a",
    "approved": "f06153980d84c395c9b7bf698b90d25eb668882bbd0a296aecf0a1b0a43462f8"
  },
  "src/app/api/kv/legacy/route.ts": {
    "historical": "10a69f3a48724d57bec54686448a632d7f6ced28067440a7a76ec5b3468c248c",
    "approved": "c8297374edac54a13dc4a03f45b4a718665781c14bf3ebc0d87633ba534804b9"
  },
  "package.json": {
    "historical": "81cfc27c470a40b9b15120704b3efc0db2e640e793ad7d0f03ddc43cbf33c55e",
    "approved": "9af95ba24f041cab39ad5686b1ab010316038cadf4a3ab658334ca261d08d342"
  }
});

const metadataPins = Object.freeze({
  "tests/deploy-history-delete-unit-plan.test.mjs": {
    "historical": "12b2aa470514a2750b960f14085c609689abcd35be03fafe189fb3d843630139",
    "approved": "18f336d85cba109baa6512ff2093593a4ac363023b9395d2496cd179c5d744d9"
  },
  "tests/deploy-history-get-unit-plan.test.mjs": {
    "historical": "d306325b23dff07f1b6212f73a48305e2a85b5afa612e0f9a97485b81c07f85e",
    "approved": "daf208c4d75ee4830e9e6181bdf9cd84e866a198198c80cb6feaf99c22591721"
  },
  "tests/deploy-start-get-unit-plan.test.mjs": {
    "historical": "a553f4a56a282c0039fe950cda9c0d38642d5210632715b12e7b0eb3b91db9c2",
    "approved": "9a815f08133fcc0a82cc461b13e258e17b0311b525082b48d5ca9396453bbe2d"
  },
  "tests/deploy-start-post-unit-plan.test.mjs": {
    "historical": "cdd8799dc01218fda3d7b47fd33bce4ef59f21e940ec958499bbcfa03156c3bc",
    "approved": "2f27fba0a5aaeb5921fac0f9b37231462d08b97916f9c04a5d738b9a44f2186d"
  },
  "tests/deploy-stop-unit-plan.test.mjs": {
    "historical": "37311fa7ce5e3a79228bc0695b5e56cec1eb4fa289d05aea111c6670c9a26266",
    "approved": "76e7909a3785163528003698ef5fd792acc4fa048b08113751a84a3e002552d4"
  },
  "tests/deploy-stream-unit-plan.test.mjs": {
    "historical": "caa9bc5899baf1f2de8fea3de5493d9745acb8655e609e98fdd0400e08393284",
    "approved": "423f2ffeffa1271dbc21aa72b796c57ee0dea47b93e6158ef67d54267bb9a822"
  },
  "tests/deployment-pods-unit-plan.test.mjs": {
    "historical": "2e7507bbc382e6596639342a9bbefa2678f024c12549a94f61841eaaf7470199",
    "approved": "e6011656426e59d6327fe6ce43da29adb14f18ba5ad9043204fc4f4b44e8ec0e"
  },
  "tests/ensure-jwt-secret-unit-plan.test.mjs": {
    "historical": "667167f27e33843a3fc7663f24c4a3fe13121b3ed609e449e9063545ca746e1a",
    "approved": "014aa6a17e87511c6aea1a16da408486a9e324f57f8ff1a02ae46f5a16fd8af1"
  },
  "tests/get-current-role-unit-plan.test.mjs": {
    "historical": "e11ff4038aa9f5d17e5d036324106d1bb9371cd51fcfbba94a2f9675c7f04092",
    "approved": "52e3d1138845199cc0b37c0474fb538e0a9cdf34ade5debb4192ca042d17350d"
  },
  "tests/get-session-account-from-headers-unit-plan.test.mjs": {
    "historical": "2a0da18ef8c3cf29db1f7678a3c4e72616812ca413928411d2279f9f10477869",
    "approved": "23ca22ee05dd7d52c04721591d3fa1b6e405face1e03f6772cc21452aaee9c1d"
  },
  "tests/get-session-account-unit-plan.test.mjs": {
    "historical": "9a36e27eaead3bdabfec5041d448ed92c619489593790e852c656cba6a29d808",
    "approved": "ff5485efee7c99795cdefdcad8ffb3e84e4135d5d2a93e11b6ef9f112ae68f6e"
  },
  "tests/get-session-from-headers-unit-plan.test.mjs": {
    "historical": "71b05c85b9523e91ee66dd13b9e32e0cd5e090cf8fc92e46e5d524ce8f77459a",
    "approved": "7db964d324ad96443140d9023c77ef555a083014f54ee23111606e1d87b1d31e"
  },
  "tests/get-session-unit-plan.test.mjs": {
    "historical": "0e17b433ae92e4a3ce5243a63ff928b2b589838f49a8e1763382fd3fe59943fb",
    "approved": "bfa401db7b27a703374670177a18a5482fcd48731a244f41680c9640699c31a3"
  },
  "tests/job-id-valid-unit-plan.test.mjs": {
    "historical": "26ffa4d641c5afd3fbe43e93617b51c74c42c2ac6a71d37e35f51af040b4ab06",
    "approved": "b8f71ff2f8e5fcfc5952af790c275da6a6c4931607a2bef9499de26c43899714"
  },
  "tests/kv-audit-route-unit-plan.test.mjs": {
    "historical": "ab99ae6e846155ef84dea15a8334a619dae109e91081c06298d2c04ffaf389df",
    "approved": "85b32edd981a421092804318b2d7f81a08ad4d0286ac5a8b2236950d0bec2482"
  },
  "tests/kv-automation-route-unit-plan.test.mjs": {
    "historical": "dae6aa7fb0891cca6ee7a467882d66e0e6dcc082b90aa5fa3160cb0ac35905a9",
    "approved": "acc7f2bf93c9a50dee68dcf0391e4bb945d95912d020ec32afd162a90c703426"
  },
  "tests/kv-config-unit-plan.test.mjs": {
    "historical": "7fc6b27c91b6846148856f3b618045733d19386a59f19359a26edaea8e9af735",
    "approved": "74675ed3e3f8c05941f37d43571508b1b3ce61f8847f14101f77dd406f242144"
  },
  "tests/kv-engine-unit-plan.test.mjs": {
    "historical": "03421b6a329a2180a466e8f428c0d35d56848c60704377c95467a7471033ab09",
    "approved": "cec7e76bf2ad792fba9cb2d5c9f2aca829c03de881d5157b14fadfdb0e1e7068"
  },
  "tests/kv-error-response-unit-plan.test.mjs": {
    "historical": "181a336fa0b46da91e4b299bd2d4f74fc723cc669b9bb0f9ddff3a726c040acc",
    "approved": "d8b37b632f9b560a21177ca6f77853d2ca7a56a0f7e90e450a5e52adcb043145"
  },
  "tests/kv-field-mapping-unit-plan.test.mjs": {
    "historical": "bb7a22dd07d40d7634755f1d0d58ab1c5e3fbcf817c837fbadbec04e90e984c8",
    "approved": "064eb403c6221dbced280c4b74315199f86ec33e60750a9d2c56fd61225e14f4"
  },
  "tests/kv-history-gc-preview-unit-plan.test.mjs": {
    "historical": "fb02b3c01cd2ca13955cee84561938996c04bde07b69e8394fb7d07b11cdcf5f",
    "approved": "1c95d9d2440a3cfb02a38d92805d54f5db08254be0d7c6feda4e9449a40ff87a"
  },
  "tests/kv-history-gc-unit-plan.test.mjs": {
    "historical": "06707ce6877d812bf333ed5a9199e7dda352938ad1bf382d4ee8a106f73b5581",
    "approved": "b33cf862332ad47e1b0ffc686c6351b4a8d8532f8ef7fe6f06ac2da1e3746134"
  },
  "tests/kv-policy-preview-unit-plan.test.mjs": {
    "historical": "2cabba939fde0c1b506615197fd750eeb317670e117357e20ba2da91be47c2f0",
    "approved": "e9b9e26f4ce6a7ffa33f8a91a69ae1a14c23d3d90acffa8e0626a131e9867a53"
  },
  "tests/kv-registry-unit-plan.test.mjs": {
    "historical": "0f35325edad89e8d440635a86cdc6b6a2c7eaee5568edbcb4d418b98f9be852f",
    "approved": "106e88f8adfbdf235b01b3be5d9c0a82145c400fce90510711606332e99e41d8"
  },
  "tests/kv-require-guarded-unit-plan.test.mjs": {
    "historical": "4dc0895e7c4bee83b5516886ac4be607a04c914d60eb6d422e30d471a939af26",
    "approved": "fea3468dcbaa6c021175bb6b773525ca42b98534e537412ccad06a3e282379e4"
  },
  "tests/observe-ansible-process-unit-plan.test.mjs": {
    "historical": "b7b8a7d56e45fea69a51ff99b90c9b83bc770939a0d8d9fc1255bcb1eadcc4d8",
    "approved": "a9e14c0bf9222147a50f4b5e30ca311f16ab2d3e620a6921c3e1ab3cf0135333"
  },
  "tests/read-job-slice-unit-plan.test.mjs": {
    "historical": "25d8859dbcf09e752220b232517c861b5bc182e20482501433e218b3f20b5fb9",
    "approved": "6e16e8eb92cf84273719b4788249e2cc7a20602c35006e1786e9c13fdf8b0bd8"
  },
  "tests/read-job-tail-unit-plan.test.mjs": {
    "historical": "cd6516e93a5201934599095f60d2aa0b5345185568414ae3dfdea9907d30ed96",
    "approved": "2bab9f49d16ac39b7bd63641bea0312c8a242a66310219a1b2480c44325c82b3"
  },
  "tests/require-access-unit-plan.test.mjs": {
    "historical": "6ad4caf6d09fc783c7256f9fb5e3eefa30f4ed9b6ed36f2e13a0f819c53b69c8",
    "approved": "28ca5592f46081b8bafb5f592157d223f2b8c3e340defb0c3b42b9aa10f9e34c"
  },
  "tests/require-operator-unit-plan.test.mjs": {
    "historical": "4d52fbca1f6efb1beeeea5780d4061b74c69b74cadf1aa1cf94d7359c51b3deb",
    "approved": "eb7a4a051f74122a8e21320e2b1ff690a67d084f778db7f9b1d946b898ffb278"
  },
  "tests/require-write-unit-plan.test.mjs": {
    "historical": "2b477ba1d4bd436008fa42cb3ccb7cdee66fd54dacbb9bef83eabd282ee8c18c",
    "approved": "4dbe5d45ef24662eb99d003d9244316fe6df19831d436afe8a79e794c77324c3"
  },
  "tests/resource-base-unit-plan.test.mjs": {
    "historical": "556d978177db618f3ab48e639b99a381855977719b10b9201ed196b8cb8b25b4",
    "approved": "e45fbe99979bade44136a8800d8aea16d83e2af4d3c0558c6fd413f74de61d71"
  }
});


// Exact manifest maintenance is separate from implementation and packaging lineages.
// Frozen caller maps retain the accepted baseline literals; mixed/unknown groups refuse.
const sensitivityPins = Object.freeze({
  "scripts/regression-sensitivity.json": {
    "baseline": "e9331ac66c8840a35f304d04f9d1135daaeaa53549df4b6e87478a7c5c9bd32b",
    "maintained": "fa48492c88b153ba1f49f8c159c1d6b695573ff1b7cb10ffe2d24fd7ee63e3f7"
  },
  "scripts/regression-sensitivity-db.json": {
    "baseline": "e4450949abc11c3c74cce2cada3089fe4188f5f236e1e3c1c206358eeba54f59",
    "maintained": "47a14c83a55c4bacc9c95c63457f5845a8329df4857e94b207fd8f319af37628"
  },
  "scripts/regression-sensitivity-process.json": {
    "baseline": "38f4e78e65c705d523139285949a8eab78508597084cdf81e9a94d85e3ec386d",
    "maintained": "f024b8fe1a6fa9e1caafeca43e505489b18b466387f18ab81a6068cff7580b29"
  }
});

export function sensitivityRevision(importer, reader = readFileSync) {
 const observed=Object.fromEntries(Object.keys(sensitivityPins).map(name=>[name,digest(reader(new URL('../'+name,importer)))]));
 const matches=['baseline','maintained'].filter(revision=>Object.entries(sensitivityPins).every(([name,pins])=>observed[name]===pins[revision]));
 assert.equal(matches.length,1,'Unknown or mixed sensitivity manifest revision');
 if(matches[0]==='maintained')assert.equal(compatibilityRevision(importer,reader),'approved','Maintained sensitivity requires approved implementation');
 return matches[0];
}

export function compatibilityRevision(importer, reader = readFileSync) {
 const observed = Object.fromEntries(Object.keys(implementationPins).map(name => [name, digest(reader(new URL("../" + name, importer)))]));
 const matches = ["historical", "approved"].filter(revision => Object.entries(implementationPins).every(([name, pins]) => observed[name] === pins[revision]));
 assert.equal(matches.length, 1, "Unknown or mixed implementation source revision");
 return matches[0];
}

export function compatibleInputHash(importer, name, historical, reader = readFileSync) {
 if(Object.hasOwn(sensitivityPins,name)){
  assert.equal(historical,sensitivityPins[name].baseline,'Historical sensitivity authority: '+name);
  return sensitivityPins[name][sensitivityRevision(importer,reader)];
 }
 const implementation=Object.hasOwn(implementationPins,name);
 if(!implementation&&!Object.hasOwn(metadataPins,name))return historical;
 const pins=implementation?implementationPins[name]:metadataPins[name];
 assert.equal(historical,pins.historical,'Historical compatibility authority: '+name);
 return pins[compatibilityRevision(importer,reader)];
}

export function assertRawPackagingInputs(importer, frozen, reader = readFileSync) {
  const lineage = packagingLineage(importer, reader);
  const pins = lineage === 'public' ? publicPins : localPins;
  const revision = compatibilityRevision(importer, reader);
  for (const [name, hash] of Object.entries(localPins)) {
    assert.equal(frozen[name], hash, 'Historical packaging authority: ' + name);
  }
  for (const [name, hash] of Object.entries(frozen)) {
    if (Object.hasOwn(implementationPins, name)) assert.equal(hash, implementationPins[name].historical, 'Historical implementation authority: ' + name);
    if (Object.hasOwn(metadataPins, name)) assert.equal(hash, metadataPins[name].historical, 'Historical metadata authority: ' + name);
    const expected = Object.hasOwn(sensitivityPins, name) ? compatibleInputHash(importer,name,hash,reader) : Object.hasOwn(pins, name) ? pins[name] : Object.hasOwn(implementationPins, name) ? implementationPins[name][revision] : Object.hasOwn(metadataPins, name) ? metadataPins[name][revision] : hash;
    assert.equal(digest(reader(new URL('../' + name, importer))), expected, name);
  }
}

export const maintainedPackagingAuthority=Object.freeze({"originalHelperSHA256":"a09dccea1580a444fc0ab21fda02b9d049848421d8b0121b0e9cab16eb7fbf15","publicSource":"cb68d87e8c02fded34c3df2421a268d8db170e29","oldDockerfile":"b442ae369248ecbcbf34b45fa3e05030477bfe03c0efa278028b7819405a3a66","currentDockerfile":"3533ac8664f7be99ab545760a4e764a405cdc80b267afb436f90359387c8643f","oldApprovedPackage":"d6fb80bcae002c25a6ced7e9553ea633db17ea2654b09518ff06f63e5b1553e2","currentApprovedPackage":"9af95ba24f041cab39ad5686b1ab010316038cadf4a3ab658334ca261d08d342","scope":"Exact raw current PUBLIC bindings; original helper and historical map/guard/function bodies preserved; no aggregate pass","oldDockerfileRelease":"d2ce23628d68783ccd80de0adcc8ddbe7d26ea11f48b4c8c4d96c7cd9e6df69e","currentDockerfileRelease":"9b936390a62c06a72138a3a42046cd68c4611fa669fc771bf24ea052df27a29b"});
