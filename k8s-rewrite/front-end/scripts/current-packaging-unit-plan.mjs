import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {readFileSync,readdirSync} from 'node:fs';
import {registerHooks} from 'node:module';
import {join,resolve} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {planFromInputs as previousPlan,executionFor as previousExecution} from './auth-register-current-unit-plan.mjs';
export {executionBatches,artifactStages,assertArtifactState,portableFixture,qualifiedNativeSHA256} from './auth-register-current-unit-plan.mjs';
import {loginMetadataDispatch,projectLoginRegistrations} from './current-login-packaging.mjs';
const digest=b=>createHash('sha256').update(b).digest('hex');
export const packagingDispatch=Object.freeze([
 {
  "original": "tests/require-access-unit-plan.test.mjs",
  "current": "tests/require-access-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-access-provenance.test.mjs",
  "start": 9234,
  "end": 84049,
  "callbackSHA256": "baa13c87e6a750eff7571fe7e4e389eae6d9dceaf8309323b3dc568720b25e6a",
  "sourceSHA256": "28ca5592f46081b8bafb5f592157d223f2b8c3e340defb0c3b42b9aa10f9e34c"
 },
 {
  "original": "tests/aggregate-unit-compatibility.test.mjs",
  "current": "tests/aggregate-compatibility-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-aggregate-compatibility-provenance.test.mjs",
  "start": 17395,
  "end": 17635,
  "callbackSHA256": "28588b69660d5e5142a0bff076f576ad12821d88d71fa6f844e9c06e36d5ce1d",
  "sourceSHA256": "ac31ae766ccff30a2b64e42580fe170340b39c81ba5b4c313fa04037333064e0"
 },
 {
  "original": "tests/kv-audit-route-unit-plan.test.mjs",
  "current": "tests/kv-audit-route-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-audit-route-provenance.test.mjs",
  "start": 8976,
  "end": 48538,
  "callbackSHA256": "3854aa9bf6c1ff577608983248b2ea45647667039c85708bf3a4b6f578628979",
  "sourceSHA256": "85b32edd981a421092804318b2d7f81a08ad4d0286ac5a8b2236950d0bec2482"
 },
 {
  "original": "tests/kv-automation-route-unit-plan.test.mjs",
  "current": "tests/kv-automation-route-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-automation-route-provenance.test.mjs",
  "start": 8919,
  "end": 48820,
  "callbackSHA256": "63ab62dee197f65dde5b37c20adc865e950a16630765af59ce31285c1353bc53",
  "sourceSHA256": "acc7f2bf93c9a50dee68dcf0391e4bb945d95912d020ec32afd162a90c703426"
 },
 {
  "original": "tests/kv-config-unit-plan.test.mjs",
  "current": "tests/kv-config-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-caller-provenance.test.mjs",
  "start": 8897,
  "end": 81109,
  "callbackSHA256": "9c7dcb82354591de9813795f702cd1cd1f70f4d4e111bcbb634f953005170787",
  "sourceSHA256": "74675ed3e3f8c05941f37d43571508b1b3ce61f8847f14101f77dd406f242144"
 },
 {
  "original": "tests/deploy-history-delete-unit-plan.test.mjs",
  "current": "tests/deploy-history-delete-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-deploy-history-delete-provenance.test.mjs",
  "start": 11763,
  "end": 15706,
  "callbackSHA256": "456b46efa8e7746d5a22e7cdb5b5ce76667bfbf58db53249e305b55f436627f7",
  "sourceSHA256": "18f336d85cba109baa6512ff2093593a4ac363023b9395d2496cd179c5d744d9"
 },
 {
  "original": "tests/deploy-history-get-unit-plan.test.mjs",
  "current": "tests/deploy-history-get-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-deploy-history-get-provenance.test.mjs",
  "start": 12037,
  "end": 16340,
  "callbackSHA256": "5ca40c64715bceabb4f4bb34fe31b516206a22df8db151991298e5fa7508de67",
  "sourceSHA256": "daf208c4d75ee4830e9e6181bdf9cd84e866a198198c80cb6feaf99c22591721"
 },
 {
  "original": "tests/deploy-start-get-unit-plan.test.mjs",
  "current": "tests/deploy-start-get-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-deploy-start-get-provenance.test.mjs",
  "start": 12187,
  "end": 16841,
  "callbackSHA256": "eaca7a4b12d646b57d9f0634445da23c76fbd32a9123082a450fcaa0f3cc7053",
  "sourceSHA256": "9a815f08133fcc0a82cc461b13e258e17b0311b525082b48d5ca9396453bbe2d"
 },
 {
  "original": "tests/deploy-start-post-unit-plan.test.mjs",
  "current": "tests/deploy-start-post-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-deploy-start-post-provenance.test.mjs",
  "start": 12377,
  "end": 17377,
  "callbackSHA256": "4a6a5a15c4a53ccc5231d17cced55f531131e480c68216ce5b0ccecf76fd6ee2",
  "sourceSHA256": "2f27fba0a5aaeb5921fac0f9b37231462d08b97916f9c04a5d738b9a44f2186d"
 },
 {
  "original": "tests/deploy-stop-unit-plan.test.mjs",
  "current": "tests/deploy-stop-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-deploy-stop-provenance.test.mjs",
  "start": 12628,
  "end": 17977,
  "callbackSHA256": "d02f57690a290e1c002c2f846529035b9073f8f132728a7bb78c9d080d4893fe",
  "sourceSHA256": "76e7909a3785163528003698ef5fd792acc4fa048b08113751a84a3e002552d4"
 },
 {
  "original": "tests/deploy-stream-unit-plan.test.mjs",
  "current": "tests/deploy-stream-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-deploy-stream-provenance.test.mjs",
  "start": 12660,
  "end": 18340,
  "callbackSHA256": "edc623a01715a21270203fba2046d4585051f48a4b1815bc791274ea897aadb7",
  "sourceSHA256": "423f2ffeffa1271dbc21aa72b796c57ee0dea47b93e6158ef67d54267bb9a822"
 },
 {
  "original": "tests/deployment-pods-unit-plan.test.mjs",
  "current": "tests/deployment-pods-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-deployment-pods-provenance.test.mjs",
  "start": 12671,
  "end": 18688,
  "callbackSHA256": "72ba250288a62fdbccd88d4db1761db3cfb83d4e7070ae4893e083fa23d70585",
  "sourceSHA256": "e6011656426e59d6327fe6ce43da29adb14f18ba5ad9043204fc4f4b44e8ec0e"
 },
 {
  "original": "tests/kv-engine-unit-plan.test.mjs",
  "current": "tests/kv-engine-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-engine-provenance.test.mjs",
  "start": 8903,
  "end": 81440,
  "callbackSHA256": "6d2ea3493e07b1a87562639d1aff20f82c31e473489f255bdd6977941dfd730d",
  "sourceSHA256": "cec7e76bf2ad792fba9cb2d5c9f2aca829c03de881d5157b14fadfdb0e1e7068"
 },
 {
  "original": "tests/ensure-jwt-secret-unit-plan.test.mjs",
  "current": "tests/ensure-jwt-secret-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-ensure-jwt-secret-provenance.test.mjs",
  "start": 12830,
  "end": 19190,
  "callbackSHA256": "aebca08fd27b8b003bede279b3433667de41e1fe8047d7c94afda4f7e3871c8d",
  "sourceSHA256": "014aa6a17e87511c6aea1a16da408486a9e324f57f8ff1a02ae46f5a16fd8af1"
 },
 {
  "original": "tests/kv-error-response-unit-plan.test.mjs",
  "current": "tests/kv-error-response-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-error-provenance.test.mjs",
  "start": 8969,
  "end": 81831,
  "callbackSHA256": "1d8403309714815520b9a85e0a7e0e72b28f5f965cbfbeda212daa34a4e61684",
  "sourceSHA256": "d8b37b632f9b560a21177ca6f77853d2ca7a56a0f7e90e450a5e52adcb043145"
 },
 {
  "original": "tests/kv-field-mapping-unit-plan.test.mjs",
  "current": "tests/kv-field-mapping-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-field-provenance.test.mjs",
  "start": 8999,
  "end": 82209,
  "callbackSHA256": "2110c5dcbfa25243fa6d1b244ae70450e4d91c99e6c5d7170976a1de0161f37c",
  "sourceSHA256": "064eb403c6221dbced280c4b74315199f86ec33e60750a9d2c56fd61225e14f4"
 },
 {
  "original": "tests/get-current-role-unit-plan.test.mjs",
  "current": "tests/get-current-role-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-get-current-role-provenance.test.mjs",
  "start": 13022,
  "end": 19730,
  "callbackSHA256": "6cb147605f2e1cc0da0d4a1c6c3082677e3c00314721a2763fe1e970d3365d37",
  "sourceSHA256": "52e3d1138845199cc0b37c0474fb538e0a9cdf34ade5debb4192ca042d17350d"
 },
 {
  "original": "tests/get-session-account-from-headers-unit-plan.test.mjs",
  "current": "tests/get-session-account-from-headers-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-get-session-account-from-headers-provenance.test.mjs",
  "start": 13546,
  "end": 20600,
  "callbackSHA256": "d386c23c922922d6ed0969a6c73ce90d96e9732c3d3a7618012eaf4e82649815",
  "sourceSHA256": "23ca22ee05dd7d52c04721591d3fa1b6e405face1e03f6772cc21452aaee9c1d"
 },
 {
  "original": "tests/get-session-account-unit-plan.test.mjs",
  "current": "tests/get-session-account-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-get-session-account-provenance.test.mjs",
  "start": 13549,
  "end": 20996,
  "callbackSHA256": "e98d4e3d8805e55f114ed7a94f7e896bbb6aecaab95275c5a1bc82a3bb667a2e",
  "sourceSHA256": "ff5485efee7c99795cdefdcad8ffb3e84e4135d5d2a93e11b6ef9f112ae68f6e"
 },
 {
  "original": "tests/get-session-from-headers-unit-plan.test.mjs",
  "current": "tests/get-session-from-headers-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-get-session-from-headers-provenance.test.mjs",
  "start": 8805,
  "end": 18958,
  "callbackSHA256": "ee7b4ca134293b75c839df944f8a1fca45c6fd8cbf747861514a4c2054ad6460",
  "sourceSHA256": "7db964d324ad96443140d9023c77ef555a083014f54ee23111606e1d87b1d31e"
 },
 {
  "original": "tests/get-session-unit-plan.test.mjs",
  "current": "tests/get-session-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-get-session-provenance.test.mjs",
  "start": 8804,
  "end": 19326,
  "callbackSHA256": "abad27df4d9fe223bc40af0d2babef028157b804b8b35f53b05aede69a562b46",
  "sourceSHA256": "bfa401db7b27a703374670177a18a5482fcd48731a244f41680c9640699c31a3"
 },
 {
  "original": "tests/kv-require-guarded-unit-plan.test.mjs",
  "current": "tests/kv-require-guarded-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-guarded-provenance.test.mjs",
  "start": 9136,
  "end": 82637,
  "callbackSHA256": "a284e578bf9e9fd15f07b8c7bb7fceac666a9a5820213b3aeb2a3e4e58b8e911",
  "sourceSHA256": "fea3468dcbaa6c021175bb6b773525ca42b98534e537412ccad06a3e282379e4"
 },
 {
  "original": "tests/kv-history-gc-unit-plan.test.mjs",
  "current": "tests/kv-history-gc-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-history-gc-provenance.test.mjs",
  "start": 9099,
  "end": 83014,
  "callbackSHA256": "bd97ab579b60f7a44165bc54b263a53bfee861124355b2cfc9eb11f32b48d4f6",
  "sourceSHA256": "b33cf862332ad47e1b0ffc686c6351b4a8d8532f8ef7fe6f06ac2da1e3746134"
 },
 {
  "original": "tests/kv-history-gc-preview-unit-plan.test.mjs",
  "current": "tests/kv-history-gc-preview-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-history-preview-provenance.test.mjs",
  "start": 9109,
  "end": 82664,
  "callbackSHA256": "2bd02ff2deab340dca23043af615847713bc41559e70215dc3a3e64aa44502db",
  "sourceSHA256": "1c95d9d2440a3cfb02a38d92805d54f5db08254be0d7c6feda4e9449a40ff87a"
 },
 {
  "original": "tests/job-id-valid-unit-plan.test.mjs",
  "current": "tests/job-id-valid-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-job-id-valid-provenance.test.mjs",
  "start": 8839,
  "end": 48068,
  "callbackSHA256": "93de502f151db84814df1935786237b4555390acedd54d207c06f163d98b2b7f",
  "sourceSHA256": "b8f71ff2f8e5fcfc5952af790c275da6a6c4931607a2bef9499de26c43899714"
 },
 {
  "original": "tests/read-job-slice-unit-plan.test.mjs",
  "current": "tests/read-job-slice-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-job-slice-provenance.test.mjs",
  "start": 9190,
  "end": 83394,
  "callbackSHA256": "b20a7e337507fec1dd9e61b1a3507b794f3515ca6eec17ae9f9cc789ba54bb3b",
  "sourceSHA256": "6e16e8eb92cf84273719b4788249e2cc7a20602c35006e1786e9c13fdf8b0bd8"
 },
 {
  "original": "tests/read-job-tail-unit-plan.test.mjs",
  "current": "tests/read-job-tail-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-job-tail-provenance.test.mjs",
  "start": 9198,
  "end": 83735,
  "callbackSHA256": "e3703965bae3802732c504fd40239b9eb8b41986fef010c1675a7c8b9b3285ea",
  "sourceSHA256": "2bab9f49d16ac39b7bd63641bea0312c8a242a66310219a1b2480c44325c82b3"
 },
 {
  "original": "tests/kv-metadata-query-unit-plan.test.mjs",
  "current": "tests/kv-metadata-query-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-metadata-query-provenance.test.mjs",
  "start": 8478,
  "end": 88472,
  "callbackSHA256": "2089e22894e085d699381090c2ca1867e4cb70567d8de6ab1d2a5aa2107d6bf7",
  "sourceSHA256": "a58fb7c160d97c9e9a696dda51cd1f8408a6dbbf38fd5d1d9f7aa6378d157a90"
 },
 {
  "original": "tests/observe-ansible-process-unit-plan.test.mjs",
  "current": "tests/observe-ansible-process-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-observe-provenance.test.mjs",
  "start": 9211,
  "end": 83054,
  "callbackSHA256": "749e086383915cd5a20c2952a4a6b633e4562ce2487859f05d449d22494cbe53",
  "sourceSHA256": "a9e14c0bf9222147a50f4b5e30ca311f16ab2d3e620a6921c3e1ab3cf0135333"
 },
 {
  "original": "tests/require-operator-unit-plan.test.mjs",
  "current": "tests/require-operator-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-operator-provenance.test.mjs",
  "start": 9270,
  "end": 84174,
  "callbackSHA256": "2e34ae10ad64f642b1ee8d5f2af9ec04724306c72fd1b714e72514a220b81db5",
  "sourceSHA256": "eb7a4a051f74122a8e21320e2b1ff690a67d084f778db7f9b1d946b898ffb278"
 },
 {
  "original": "tests/kv-parse-actions-unit-plan.test.mjs",
  "current": "tests/kv-parse-actions-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-parse-actions-provenance.test.mjs",
  "start": 8499,
  "end": 88835,
  "callbackSHA256": "5c8987083168808a8ec1760bc80be610e356c887d37cdbd530c78f0227ec0b98",
  "sourceSHA256": "5584298ee8f291233fffaf2c81b3fc21799648d94726e9e031fa616661e9c2d9"
 },
 {
  "original": "tests/kv-policy-allows-unit-plan.test.mjs",
  "current": "tests/kv-policy-allows-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-policy-allows-provenance.test.mjs",
  "start": 8541,
  "end": 89216,
  "callbackSHA256": "e32be141158466c30352c649fb901deeb568b28a5d71fff7d026576ad592d962",
  "sourceSHA256": "2606491810961798c725cd8e3139a0c44c84a079f4498bcb7f746778561589d7"
 },
 {
  "original": "tests/kv-policy-preview-unit-plan.test.mjs",
  "current": "tests/kv-policy-preview-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-policy-preview-provenance.test.mjs",
  "start": 9143,
  "end": 81992,
  "callbackSHA256": "370290e8060cde441cc270774c0553a3b0d1fa632638e3c017b71e437c74aedf",
  "sourceSHA256": "e9b9e26f4ce6a7ffa33f8a91a69ae1a14c23d3d90acffa8e0626a131e9867a53"
 },
 {
  "original": "tests/kv-registry-unit-plan.test.mjs",
  "current": "tests/kv-registry-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-registry-provenance.test.mjs",
  "start": 9080,
  "end": 82256,
  "callbackSHA256": "51968169d9f0d2ea7f2e2f0f4a3b4b0dbb1c0d0029345e21ae4ac70ed28dc655",
  "sourceSHA256": "106e88f8adfbdf235b01b3be5d9c0a82145c400fce90510711606332e99e41d8"
 },
 {
  "original": "tests/resource-base-unit-plan.test.mjs",
  "current": "tests/resource-base-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-resource-base-provenance.test.mjs",
  "start": 9342,
  "end": 84943,
  "callbackSHA256": "103596160bc1aacc835958ea22cfa8322824bf1aba785ffc80685ae17aedb61b",
  "sourceSHA256": "e45fbe99979bade44136a8800d8aea16d83e2af4d3c0558c6fd413f74de61d71"
 },
 {
  "original": "tests/resource-cache-unit-plan.test.mjs",
  "current": "tests/resource-cache-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-resource-cache-provenance.test.mjs",
  "start": 8299,
  "end": 83549,
  "callbackSHA256": "94506789c600197e4274edbc661fc6727b1095343cb68d7125f1e6dc43a65567",
  "sourceSHA256": "d9d76911bf960e657f35c2bd9a6d43944faf503ee52699cc395153d741b9458b"
 },
 {
  "original": "tests/resource-capabilities-unit-plan.test.mjs",
  "current": "tests/resource-capabilities-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-resource-capabilities-provenance.test.mjs",
  "start": 8471,
  "end": 84746,
  "callbackSHA256": "e26e873c25206b7123c398f5b818b3991abfe6f4178e6a276f109df0355ea501",
  "sourceSHA256": "0966fd42dcdf0815b9796a5ae8369aae31b52f1ab8210a8f2f7728850bd17f25"
 },
 {
  "original": "tests/resource-private-state-unit-plan.test.mjs",
  "current": "tests/resource-private-state-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-resource-private-state-provenance.test.mjs",
  "start": 8676,
  "end": 84621,
  "callbackSHA256": "418b92c8cddaac026fce5d70e5797d782ac8c04e86c4b13bc3f0ee88f1328846",
  "sourceSHA256": "0a236ca2d8cd09f66bc64169fa8bc747526e6cafe7a75a7323d8dff2e97bdf44"
 },
 {
  "original": "tests/resource-snapshot-unit-plan.test.mjs",
  "current": "tests/resource-snapshot-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-resource-snapshot-provenance.test.mjs",
  "start": 8770,
  "end": 85773,
  "callbackSHA256": "b917b674ede881fd7f9509665a686043a85d7eb4847676aa33882b9928a265a7",
  "sourceSHA256": "5028761ae8124d0cce7113cbe283e6e23f5140566b97e0962afa0d686cc3de9a"
 },
 {
  "original": "tests/resource-state-unit-plan.test.mjs",
  "current": "tests/resource-state-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-resource-state-provenance.test.mjs",
  "start": 8598,
  "end": 85946,
  "callbackSHA256": "ad62687954c14ab08e55470e4fb083e211c4e0be0c7fd29e0cce340ea4f5a142",
  "sourceSHA256": "21b2da623b3460eeb4ff3e02d86131ea4b63751d0c0ebdbcf9c768bb5002337f"
 },
 {
  "original": "tests/runtime-capabilities-unit-plan.test.mjs",
  "current": "tests/runtime-capabilities-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-runtime-capabilities-provenance.test.mjs",
  "start": 8514,
  "end": 85494,
  "callbackSHA256": "eb27b9ed3c8e25072e04fc2aa3a8526a97052779507ae84bed0c883fb1004248",
  "sourceSHA256": "b138b646c46faa578bdf6368324524cbf0137a746e61902f343b7f550bee4f20"
 },
 {
  "original": "tests/secret-flat-summary-unit-plan.test.mjs",
  "current": "tests/secret-flat-summary-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-secret-flat-summary-provenance.test.mjs",
  "start": 8824,
  "end": 88471,
  "callbackSHA256": "73e9a76c4bb7731dee4f2253200d24651d8f52ad6ba7ffdcc731464c69e45be9",
  "sourceSHA256": "23cb996605395e73a7401edce01a0f18e3788bb8b0f886ac42424ae538c599f3"
 },
 {
  "original": "tests/settings-mutation-unit-plan.test.mjs",
  "current": "tests/settings-mutation-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-settings-mutation-provenance.test.mjs",
  "start": 8570,
  "end": 87873,
  "callbackSHA256": "a7b48114f0f00ed655d76a4ff311bde8eaf8767841abde7db68e7528e59afa1c",
  "sourceSHA256": "c9d62c2825993dc9583ab225809838d0a894a43bbe28d3b860ad3fdc8db3aef1"
 },
 {
  "original": "tests/shared-metadata-query-unit-plan.test.mjs",
  "current": "tests/shared-metadata-query-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-shared-metadata-query-provenance.test.mjs",
  "start": 8613,
  "end": 85944,
  "callbackSHA256": "4c637094400fe51956f8bba700b68cff8c5777fbfd76abebdba48d79917b281d",
  "sourceSHA256": "6788d3c4fcd9b401124d24c4097a4052d606992e60f7bce1c0630ea44c62e849"
 },
 {
  "original": "tests/sign-jwt-unit-plan.test.mjs",
  "current": "tests/sign-jwt-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-sign-jwt-provenance.test.mjs",
  "start": 8942,
  "end": 86627,
  "callbackSHA256": "df20474ea38d015d4ce93368e8ff83d8c6d2f105698f248ff6beeacdc6de442e",
  "sourceSHA256": "d9717844b80f17cb52b1a30615aa0b8f881fc0522611b9066eba4b4e4f714839"
 },
 {
  "original": "tests/verify-jwt-unit-plan.test.mjs",
  "current": "tests/verify-jwt-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-verify-jwt-provenance.test.mjs",
  "start": 8945,
  "end": 86945,
  "callbackSHA256": "a2a0d2b0db307462565fc9285c56a99d59d05367250aac72340b75dfff8df52f",
  "sourceSHA256": "3332c7d469ae267c14e6c46f18124b1898f0d5d2cfbf6d724143f7b3a20e94ad"
 },
 {
  "original": "tests/welcome-navigation-unit-plan.test.mjs",
  "current": "tests/welcome-navigation-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-welcome-navigation-provenance.test.mjs",
  "start": 8201,
  "end": 86519,
  "callbackSHA256": "3c2efe764919561b4030dd09838803055a47f5cd724144516979f342322d5302",
  "sourceSHA256": "905bedd61eae26ba0c8d49605abebf99085ee7528765c209053842f97fb3ef86"
 },
 {
  "original": "tests/worker-reader-unit-plan.test.mjs",
  "current": "tests/worker-reader-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-worker-reader-provenance.test.mjs",
  "start": 8416,
  "end": 87071,
  "callbackSHA256": "6899d4202363f1e6ee3a4421f8978df8c456a9253d89379be667fc3bcf20ab7e",
  "sourceSHA256": "bd973a1da534f96cf45b45a6a3ef71cf8e6c56620b093386ce65fd3b82bbe97b"
 },
 {
  "original": "tests/require-write-unit-plan.test.mjs",
  "current": "tests/require-write-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-write-provenance.test.mjs",
  "start": 9281,
  "end": 84524,
  "callbackSHA256": "9a6d0a8d1a321ea1edbf6db84579c4a4a062eaeac6a7a8e012a8bac902052ea1",
  "sourceSHA256": "4dbe5d45ef24662eb99d003d9244316fe6df19831d436afe8a79e794c77324c3"
 },
 {
  "original": "tests/yaml-save-unit-plan.test.mjs",
  "current": "tests/yaml-save-current-packaging.test.mjs",
  "metadata": "tests/current-packaging-yaml-save-provenance.test.mjs",
  "start": 8175,
  "end": 87160,
  "callbackSHA256": "84b0dc37ddaf064cc2cdc593a3dd9109f297a6ec9789681a7af04da6f4face65",
  "sourceSHA256": "8ab70adcbea96507d77029aafdae52361201bf24a225f4429516f2f923e39812"
 }
].map(row=>Object.freeze(row)));
export const publicCheckpoint='afc2adfa23bf32b026ae3cea9b3390a70096adcf';
const inventorySHA256='f38ddef829ae2443e2064036e49a5b87fc897d3126b78a67c121bc61795ebe80';
// This is Git object authority, not authentication of a live filesystem.
export function assertPublicAuthority(gitDir){
 assert.ok(typeof gitDir==='string'&&gitDir.length>0,'Explicit readonly PUBLIC Git object authority required');
 const result=spawnSync('git',['-c','safe.directory='+gitDir,'--git-dir='+gitDir,'ls-tree','-r','-z',publicCheckpoint,'--','k8s-rewrite/front-end/'],{encoding:'utf8',maxBuffer:4*1024*1024,timeout:20000});
 assert.equal(result.error,undefined,'PUBLIC Git authority unavailable');assert.equal(result.status,0,'PUBLIC Git inventory unavailable');
 const rows=result.stdout.split('\0').filter(Boolean).map(line=>{
  const [meta,path]=line.split('\t'),[mode,kind,blob]=meta.split(' ');assert.equal(kind,'blob');
  return [path.slice('k8s-rewrite/front-end/'.length),mode,blob];
 });
 assert.equal(rows.length,986,'Complete PUBLIC inventory required');assert.equal(digest(JSON.stringify(rows)),inventorySHA256,'PUBLIC inventory changed');
 return Object.freeze({publicCheckpoint,inventorySHA256,files:rows.length});
}
export function withPackagingDispatch(prior){
 assert.equal(new Set(prior.selected).size,prior.selected.length,'Duplicate selected input');
 for(const row of [...packagingDispatch,loginMetadataDispatch])for(const path of [row.original,row.current,row.metadata])
  assert.equal(prior.selected.filter(n=>n===path).length,1,'Required packaging input exactly once: '+path);
 return {...prior,packagingDispatch,scope:prior.scope+' Exact selected packaging registrations dispatched; all neighbouring controls retained. Not an aggregate pass.'};
}
export function planFromInputs(names,read,gitDir=process.env.BORTUS_PACKAGING_PUBLIC_GIT_DIR){
 const publicAuthority=assertPublicAuthority(gitDir);
 return {...withPackagingDispatch(previousPlan(names,read)),publicAuthority};
}
export function unitTestPlan(root){return planFromInputs(readdirSync(join(root,'tests')),name=>readFileSync(join(root,name),'utf8'));}
export function executionFor(plan,args){
 if(args.length===2&&args[0]==='--group'&&args[1]==='current-login-packaging')return [loginMetadataDispatch.original,loginMetadataDispatch.current,loginMetadataDispatch.metadata];
 if(args.length===2&&args[0]==='--group'&&args[1]==='current-packaging'){
  const wanted=new Set(packagingDispatch.flatMap(r=>[r.original,r.current,r.metadata]));return plan.selected.filter(n=>wanted.has(n));
 }
 const selected=previousExecution(plan,args),wanted=new Set(selected);
 for(const row of [...packagingDispatch,loginMetadataDispatch])if(wanted.has(row.original)){wanted.add(row.current);wanted.add(row.metadata);}
 return [...selected,...plan.selected.filter(n=>wanted.has(n)&&!selected.includes(n))];
}
// Remove only the exact frozen registration. Its qualified current projection
// and metadata stay selected once; no skip flag or altered historical file.
export function projectRegistration(bytes,row){
 assert.ok(packagingDispatch.includes(row),'Unknown packaging caller');assert.ok(Buffer.isBuffer(bytes),'Raw Buffer required');
 assert.equal(digest(bytes),row.sourceSHA256,'Historical caller raw bytes changed');
 assert.equal(digest(bytes.subarray(row.start,row.end)),row.callbackSHA256,'Historical registration changed');
 const replacement=Buffer.from('/* Packaging registration dispatched to '+row.current+'; neighbours retained. */');
 return Buffer.concat([bytes.subarray(0,row.start),replacement,bytes.subarray(row.end)]);
}
export function dispatchForBatch(root,files){
 const callers=[...packagingDispatch,loginMetadataDispatch].filter(r=>files.includes(r.original)).map(r=>r.original);
 return callers.length?{flags:['--import',pathToFileURL(join(root,'scripts/current-packaging-unit-plan.mjs')).href],env:{BORTUS_PACKAGING_DISPATCH:JSON.stringify({root:resolve(root),callers})}}:{flags:[],env:{BORTUS_PACKAGING_DISPATCH:''}};
}
export function installPackagingHooks(context){
 assertPublicAuthority(process.env.BORTUS_PACKAGING_PUBLIC_GIT_DIR);
 assert.ok(context&&typeof context.root==='string'&&resolve(context.root)===context.root&&Array.isArray(context.callers),'Invalid dispatch context');
 assert.equal(new Set(context.callers).size,context.callers.length,'Duplicate dispatch caller');
 const targets=new Map(context.callers.map(name=>{
  const row=[...packagingDispatch,loginMetadataDispatch].find(r=>r.original===name);assert.ok(row,'Unknown dispatch caller');
  return [pathToFileURL(join(context.root,name)).href,row];
 }));
 return registerHooks({load(url,context,nextLoad){
  const row=targets.get(url);if(!row)return nextLoad(url,context);
  const bytes=readFileSync(fileURLToPath(url));return {format:'module',shortCircuit:true,source:row===loginMetadataDispatch?projectLoginRegistrations(bytes):projectRegistration(bytes,row)};
 }});
}
if(process.env.BORTUS_PACKAGING_DISPATCH)installPackagingHooks(JSON.parse(process.env.BORTUS_PACKAGING_DISPATCH));
