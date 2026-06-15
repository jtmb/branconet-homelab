/*
 * ATTENTION: An "eval-source-map" devtool has been used.
 * This devtool is neither made for production nor for readable output files.
 * It uses "eval()" calls to create a separate source file with attached SourceMaps in the browser devtools.
 * If you are trying to read the output file, select a different devtool (https://webpack.js.org/configuration/devtool/)
 * or disable the default devtool with "devtool: false".
 * If you are looking for production-ready output files, see mode: "production" (https://webpack.js.org/configuration/mode/).
 */
(() => {
var exports = {};
exports.id = "app/api/vars/route";
exports.ids = ["app/api/vars/route"];
exports.modules = {

/***/ "@prisma/client":
/*!*********************************!*\
  !*** external "@prisma/client" ***!
  \*********************************/
/***/ ((module) => {

"use strict";
module.exports = require("@prisma/client");

/***/ }),

/***/ "next/dist/compiled/next-server/app-page.runtime.dev.js":
/*!*************************************************************************!*\
  !*** external "next/dist/compiled/next-server/app-page.runtime.dev.js" ***!
  \*************************************************************************/
/***/ ((module) => {

"use strict";
module.exports = require("next/dist/compiled/next-server/app-page.runtime.dev.js");

/***/ }),

/***/ "next/dist/compiled/next-server/app-route.runtime.dev.js":
/*!**************************************************************************!*\
  !*** external "next/dist/compiled/next-server/app-route.runtime.dev.js" ***!
  \**************************************************************************/
/***/ ((module) => {

"use strict";
module.exports = require("next/dist/compiled/next-server/app-route.runtime.dev.js");

/***/ }),

/***/ "../app-render/work-async-storage.external":
/*!*****************************************************************************!*\
  !*** external "next/dist/server/app-render/work-async-storage.external.js" ***!
  \*****************************************************************************/
/***/ ((module) => {

"use strict";
module.exports = require("next/dist/server/app-render/work-async-storage.external.js");

/***/ }),

/***/ "./work-unit-async-storage.external":
/*!**********************************************************************************!*\
  !*** external "next/dist/server/app-render/work-unit-async-storage.external.js" ***!
  \**********************************************************************************/
/***/ ((module) => {

"use strict";
module.exports = require("next/dist/server/app-render/work-unit-async-storage.external.js");

/***/ }),

/***/ "(rsc)/./node_modules/next/dist/build/webpack/loaders/next-app-loader/index.js?name=app%2Fapi%2Fvars%2Froute&page=%2Fapi%2Fvars%2Froute&appPaths=&pagePath=private-next-app-dir%2Fapi%2Fvars%2Froute.ts&appDir=%2Fhome%2Fbrajam%2Frepos%2Fbranconet-homelab%2Fk8s-rewrite%2Ffront-end%2Fsrc%2Fapp&pageExtensions=tsx&pageExtensions=ts&pageExtensions=jsx&pageExtensions=js&rootDir=%2Fhome%2Fbrajam%2Frepos%2Fbranconet-homelab%2Fk8s-rewrite%2Ffront-end&isDev=true&tsconfigPath=tsconfig.json&basePath=&assetPrefix=&nextConfigOutput=&preferredRegion=&middlewareConfig=e30%3D!":
/*!************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************!*\
  !*** ./node_modules/next/dist/build/webpack/loaders/next-app-loader/index.js?name=app%2Fapi%2Fvars%2Froute&page=%2Fapi%2Fvars%2Froute&appPaths=&pagePath=private-next-app-dir%2Fapi%2Fvars%2Froute.ts&appDir=%2Fhome%2Fbrajam%2Frepos%2Fbranconet-homelab%2Fk8s-rewrite%2Ffront-end%2Fsrc%2Fapp&pageExtensions=tsx&pageExtensions=ts&pageExtensions=jsx&pageExtensions=js&rootDir=%2Fhome%2Fbrajam%2Frepos%2Fbranconet-homelab%2Fk8s-rewrite%2Ffront-end&isDev=true&tsconfigPath=tsconfig.json&basePath=&assetPrefix=&nextConfigOutput=&preferredRegion=&middlewareConfig=e30%3D! ***!
  \************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************/
/***/ ((__unused_webpack_module, __webpack_exports__, __webpack_require__) => {

"use strict";
eval("__webpack_require__.r(__webpack_exports__);\n/* harmony export */ __webpack_require__.d(__webpack_exports__, {\n/* harmony export */   patchFetch: () => (/* binding */ patchFetch),\n/* harmony export */   routeModule: () => (/* binding */ routeModule),\n/* harmony export */   serverHooks: () => (/* binding */ serverHooks),\n/* harmony export */   workAsyncStorage: () => (/* binding */ workAsyncStorage),\n/* harmony export */   workUnitAsyncStorage: () => (/* binding */ workUnitAsyncStorage)\n/* harmony export */ });\n/* harmony import */ var next_dist_server_route_modules_app_route_module_compiled__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! next/dist/server/route-modules/app-route/module.compiled */ \"(rsc)/./node_modules/next/dist/server/route-modules/app-route/module.compiled.js\");\n/* harmony import */ var next_dist_server_route_modules_app_route_module_compiled__WEBPACK_IMPORTED_MODULE_0___default = /*#__PURE__*/__webpack_require__.n(next_dist_server_route_modules_app_route_module_compiled__WEBPACK_IMPORTED_MODULE_0__);\n/* harmony import */ var next_dist_server_route_kind__WEBPACK_IMPORTED_MODULE_1__ = __webpack_require__(/*! next/dist/server/route-kind */ \"(rsc)/./node_modules/next/dist/server/route-kind.js\");\n/* harmony import */ var next_dist_server_lib_patch_fetch__WEBPACK_IMPORTED_MODULE_2__ = __webpack_require__(/*! next/dist/server/lib/patch-fetch */ \"(rsc)/./node_modules/next/dist/server/lib/patch-fetch.js\");\n/* harmony import */ var next_dist_server_lib_patch_fetch__WEBPACK_IMPORTED_MODULE_2___default = /*#__PURE__*/__webpack_require__.n(next_dist_server_lib_patch_fetch__WEBPACK_IMPORTED_MODULE_2__);\n/* harmony import */ var _home_brajam_repos_branconet_homelab_k8s_rewrite_front_end_src_app_api_vars_route_ts__WEBPACK_IMPORTED_MODULE_3__ = __webpack_require__(/*! ./src/app/api/vars/route.ts */ \"(rsc)/./src/app/api/vars/route.ts\");\n\n\n\n\n// We inject the nextConfigOutput here so that we can use them in the route\n// module.\nconst nextConfigOutput = \"\"\nconst routeModule = new next_dist_server_route_modules_app_route_module_compiled__WEBPACK_IMPORTED_MODULE_0__.AppRouteRouteModule({\n    definition: {\n        kind: next_dist_server_route_kind__WEBPACK_IMPORTED_MODULE_1__.RouteKind.APP_ROUTE,\n        page: \"/api/vars/route\",\n        pathname: \"/api/vars\",\n        filename: \"route\",\n        bundlePath: \"app/api/vars/route\"\n    },\n    resolvedPagePath: \"/home/brajam/repos/branconet-homelab/k8s-rewrite/front-end/src/app/api/vars/route.ts\",\n    nextConfigOutput,\n    userland: _home_brajam_repos_branconet_homelab_k8s_rewrite_front_end_src_app_api_vars_route_ts__WEBPACK_IMPORTED_MODULE_3__\n});\n// Pull out the exports that we need to expose from the module. This should\n// be eliminated when we've moved the other routes to the new format. These\n// are used to hook into the route.\nconst { workAsyncStorage, workUnitAsyncStorage, serverHooks } = routeModule;\nfunction patchFetch() {\n    return (0,next_dist_server_lib_patch_fetch__WEBPACK_IMPORTED_MODULE_2__.patchFetch)({\n        workAsyncStorage,\n        workUnitAsyncStorage\n    });\n}\n\n\n//# sourceMappingURL=app-route.js.map//# sourceURL=[module]\n//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiKHJzYykvLi9ub2RlX21vZHVsZXMvbmV4dC9kaXN0L2J1aWxkL3dlYnBhY2svbG9hZGVycy9uZXh0LWFwcC1sb2FkZXIvaW5kZXguanM/bmFtZT1hcHAlMkZhcGklMkZ2YXJzJTJGcm91dGUmcGFnZT0lMkZhcGklMkZ2YXJzJTJGcm91dGUmYXBwUGF0aHM9JnBhZ2VQYXRoPXByaXZhdGUtbmV4dC1hcHAtZGlyJTJGYXBpJTJGdmFycyUyRnJvdXRlLnRzJmFwcERpcj0lMkZob21lJTJGYnJhamFtJTJGcmVwb3MlMkZicmFuY29uZXQtaG9tZWxhYiUyRms4cy1yZXdyaXRlJTJGZnJvbnQtZW5kJTJGc3JjJTJGYXBwJnBhZ2VFeHRlbnNpb25zPXRzeCZwYWdlRXh0ZW5zaW9ucz10cyZwYWdlRXh0ZW5zaW9ucz1qc3gmcGFnZUV4dGVuc2lvbnM9anMmcm9vdERpcj0lMkZob21lJTJGYnJhamFtJTJGcmVwb3MlMkZicmFuY29uZXQtaG9tZWxhYiUyRms4cy1yZXdyaXRlJTJGZnJvbnQtZW5kJmlzRGV2PXRydWUmdHNjb25maWdQYXRoPXRzY29uZmlnLmpzb24mYmFzZVBhdGg9JmFzc2V0UHJlZml4PSZuZXh0Q29uZmlnT3V0cHV0PSZwcmVmZXJyZWRSZWdpb249Jm1pZGRsZXdhcmVDb25maWc9ZTMwJTNEISIsIm1hcHBpbmdzIjoiOzs7Ozs7Ozs7Ozs7OztBQUErRjtBQUN2QztBQUNxQjtBQUNvQztBQUNqSDtBQUNBO0FBQ0E7QUFDQSx3QkFBd0IseUdBQW1CO0FBQzNDO0FBQ0EsY0FBYyxrRUFBUztBQUN2QjtBQUNBO0FBQ0E7QUFDQTtBQUNBLEtBQUs7QUFDTDtBQUNBO0FBQ0EsWUFBWTtBQUNaLENBQUM7QUFDRDtBQUNBO0FBQ0E7QUFDQSxRQUFRLHNEQUFzRDtBQUM5RDtBQUNBLFdBQVcsNEVBQVc7QUFDdEI7QUFDQTtBQUNBLEtBQUs7QUFDTDtBQUMwRjs7QUFFMUYiLCJzb3VyY2VzIjpbIndlYnBhY2s6Ly9icmFuY29uZXQtazhzLW1hbmFnZXIvP2RkOWQiXSwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgQXBwUm91dGVSb3V0ZU1vZHVsZSB9IGZyb20gXCJuZXh0L2Rpc3Qvc2VydmVyL3JvdXRlLW1vZHVsZXMvYXBwLXJvdXRlL21vZHVsZS5jb21waWxlZFwiO1xuaW1wb3J0IHsgUm91dGVLaW5kIH0gZnJvbSBcIm5leHQvZGlzdC9zZXJ2ZXIvcm91dGUta2luZFwiO1xuaW1wb3J0IHsgcGF0Y2hGZXRjaCBhcyBfcGF0Y2hGZXRjaCB9IGZyb20gXCJuZXh0L2Rpc3Qvc2VydmVyL2xpYi9wYXRjaC1mZXRjaFwiO1xuaW1wb3J0ICogYXMgdXNlcmxhbmQgZnJvbSBcIi9ob21lL2JyYWphbS9yZXBvcy9icmFuY29uZXQtaG9tZWxhYi9rOHMtcmV3cml0ZS9mcm9udC1lbmQvc3JjL2FwcC9hcGkvdmFycy9yb3V0ZS50c1wiO1xuLy8gV2UgaW5qZWN0IHRoZSBuZXh0Q29uZmlnT3V0cHV0IGhlcmUgc28gdGhhdCB3ZSBjYW4gdXNlIHRoZW0gaW4gdGhlIHJvdXRlXG4vLyBtb2R1bGUuXG5jb25zdCBuZXh0Q29uZmlnT3V0cHV0ID0gXCJcIlxuY29uc3Qgcm91dGVNb2R1bGUgPSBuZXcgQXBwUm91dGVSb3V0ZU1vZHVsZSh7XG4gICAgZGVmaW5pdGlvbjoge1xuICAgICAgICBraW5kOiBSb3V0ZUtpbmQuQVBQX1JPVVRFLFxuICAgICAgICBwYWdlOiBcIi9hcGkvdmFycy9yb3V0ZVwiLFxuICAgICAgICBwYXRobmFtZTogXCIvYXBpL3ZhcnNcIixcbiAgICAgICAgZmlsZW5hbWU6IFwicm91dGVcIixcbiAgICAgICAgYnVuZGxlUGF0aDogXCJhcHAvYXBpL3ZhcnMvcm91dGVcIlxuICAgIH0sXG4gICAgcmVzb2x2ZWRQYWdlUGF0aDogXCIvaG9tZS9icmFqYW0vcmVwb3MvYnJhbmNvbmV0LWhvbWVsYWIvazhzLXJld3JpdGUvZnJvbnQtZW5kL3NyYy9hcHAvYXBpL3ZhcnMvcm91dGUudHNcIixcbiAgICBuZXh0Q29uZmlnT3V0cHV0LFxuICAgIHVzZXJsYW5kXG59KTtcbi8vIFB1bGwgb3V0IHRoZSBleHBvcnRzIHRoYXQgd2UgbmVlZCB0byBleHBvc2UgZnJvbSB0aGUgbW9kdWxlLiBUaGlzIHNob3VsZFxuLy8gYmUgZWxpbWluYXRlZCB3aGVuIHdlJ3ZlIG1vdmVkIHRoZSBvdGhlciByb3V0ZXMgdG8gdGhlIG5ldyBmb3JtYXQuIFRoZXNlXG4vLyBhcmUgdXNlZCB0byBob29rIGludG8gdGhlIHJvdXRlLlxuY29uc3QgeyB3b3JrQXN5bmNTdG9yYWdlLCB3b3JrVW5pdEFzeW5jU3RvcmFnZSwgc2VydmVySG9va3MgfSA9IHJvdXRlTW9kdWxlO1xuZnVuY3Rpb24gcGF0Y2hGZXRjaCgpIHtcbiAgICByZXR1cm4gX3BhdGNoRmV0Y2goe1xuICAgICAgICB3b3JrQXN5bmNTdG9yYWdlLFxuICAgICAgICB3b3JrVW5pdEFzeW5jU3RvcmFnZVxuICAgIH0pO1xufVxuZXhwb3J0IHsgcm91dGVNb2R1bGUsIHdvcmtBc3luY1N0b3JhZ2UsIHdvcmtVbml0QXN5bmNTdG9yYWdlLCBzZXJ2ZXJIb29rcywgcGF0Y2hGZXRjaCwgIH07XG5cbi8vIyBzb3VyY2VNYXBwaW5nVVJMPWFwcC1yb3V0ZS5qcy5tYXAiXSwibmFtZXMiOltdLCJzb3VyY2VSb290IjoiIn0=\n//# sourceURL=webpack-internal:///(rsc)/./node_modules/next/dist/build/webpack/loaders/next-app-loader/index.js?name=app%2Fapi%2Fvars%2Froute&page=%2Fapi%2Fvars%2Froute&appPaths=&pagePath=private-next-app-dir%2Fapi%2Fvars%2Froute.ts&appDir=%2Fhome%2Fbrajam%2Frepos%2Fbranconet-homelab%2Fk8s-rewrite%2Ffront-end%2Fsrc%2Fapp&pageExtensions=tsx&pageExtensions=ts&pageExtensions=jsx&pageExtensions=js&rootDir=%2Fhome%2Fbrajam%2Frepos%2Fbranconet-homelab%2Fk8s-rewrite%2Ffront-end&isDev=true&tsconfigPath=tsconfig.json&basePath=&assetPrefix=&nextConfigOutput=&preferredRegion=&middlewareConfig=e30%3D!\n");

/***/ }),

/***/ "(ssr)/./node_modules/next/dist/build/webpack/loaders/next-flight-client-entry-loader.js?server=true!":
/*!******************************************************************************************************!*\
  !*** ./node_modules/next/dist/build/webpack/loaders/next-flight-client-entry-loader.js?server=true! ***!
  \******************************************************************************************************/
/***/ (() => {



/***/ }),

/***/ "(rsc)/./src/app/api/vars/route.ts":
/*!***********************************!*\
  !*** ./src/app/api/vars/route.ts ***!
  \***********************************/
/***/ ((__unused_webpack_module, __webpack_exports__, __webpack_require__) => {

"use strict";
eval("__webpack_require__.r(__webpack_exports__);\n/* harmony export */ __webpack_require__.d(__webpack_exports__, {\n/* harmony export */   GET: () => (/* binding */ GET),\n/* harmony export */   POST: () => (/* binding */ POST)\n/* harmony export */ });\n/* harmony import */ var next_server__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! next/server */ \"(rsc)/./node_modules/next/dist/api/server.js\");\n/* harmony import */ var _lib_db__WEBPACK_IMPORTED_MODULE_1__ = __webpack_require__(/*! @/lib/db */ \"(rsc)/./src/lib/db.ts\");\n\n\nasync function GET() {\n    const vars = await _lib_db__WEBPACK_IMPORTED_MODULE_1__[\"default\"].variable.findMany({\n        orderBy: {\n            category: \"asc\"\n        }\n    });\n    return next_server__WEBPACK_IMPORTED_MODULE_0__.NextResponse.json(vars);\n}\nasync function POST(request) {\n    try {\n        const body = await request.json();\n        const { id, key, value, category, encrypted } = body;\n        if (id) {\n            // Update existing variable\n            const existing = await _lib_db__WEBPACK_IMPORTED_MODULE_1__[\"default\"].variable.findUnique({\n                where: {\n                    id\n                }\n            });\n            if (existing) {\n                const updated = await _lib_db__WEBPACK_IMPORTED_MODULE_1__[\"default\"].variable.update({\n                    where: {\n                        id\n                    },\n                    data: {\n                        key: key || existing.key,\n                        value: value ?? existing.value,\n                        category: category || existing.category,\n                        encrypted: encrypted ?? existing.encrypted\n                    }\n                });\n                return next_server__WEBPACK_IMPORTED_MODULE_0__.NextResponse.json({\n                    success: true,\n                    variable: updated\n                });\n            }\n        }\n        // Create new variable\n        const created = await _lib_db__WEBPACK_IMPORTED_MODULE_1__[\"default\"].variable.create({\n            data: {\n                key: key || \"new_var\",\n                value: value || \"\",\n                category: category || \"general\",\n                encrypted: encrypted || false\n            }\n        });\n        return next_server__WEBPACK_IMPORTED_MODULE_0__.NextResponse.json({\n            success: true,\n            variable: created\n        }, {\n            status: 201\n        });\n    } catch (err) {\n        return next_server__WEBPACK_IMPORTED_MODULE_0__.NextResponse.json({\n            error: \"Invalid request\"\n        }, {\n            status: 400\n        });\n    }\n}\n//# sourceURL=[module]\n//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiKHJzYykvLi9zcmMvYXBwL2FwaS92YXJzL3JvdXRlLnRzIiwibWFwcGluZ3MiOiI7Ozs7Ozs7QUFBd0Q7QUFDMUI7QUFFdkIsZUFBZUU7SUFDcEIsTUFBTUMsT0FBTyxNQUFNRiwrQ0FBTUEsQ0FBQ0csUUFBUSxDQUFDQyxRQUFRLENBQUM7UUFDMUNDLFNBQVM7WUFBRUMsVUFBVTtRQUFNO0lBQzdCO0lBQ0EsT0FBT1AscURBQVlBLENBQUNRLElBQUksQ0FBQ0w7QUFDM0I7QUFFTyxlQUFlTSxLQUFLQyxPQUFvQjtJQUM3QyxJQUFJO1FBQ0YsTUFBTUMsT0FBTyxNQUFNRCxRQUFRRixJQUFJO1FBQy9CLE1BQU0sRUFBRUksRUFBRSxFQUFFQyxHQUFHLEVBQUVDLEtBQUssRUFBRVAsUUFBUSxFQUFFUSxTQUFTLEVBQUUsR0FBR0o7UUFFaEQsSUFBSUMsSUFBSTtZQUNOLDJCQUEyQjtZQUMzQixNQUFNSSxXQUFXLE1BQU1mLCtDQUFNQSxDQUFDRyxRQUFRLENBQUNhLFVBQVUsQ0FBQztnQkFBRUMsT0FBTztvQkFBRU47Z0JBQUc7WUFBRTtZQUNsRSxJQUFJSSxVQUFVO2dCQUNaLE1BQU1HLFVBQVUsTUFBTWxCLCtDQUFNQSxDQUFDRyxRQUFRLENBQUNnQixNQUFNLENBQUM7b0JBQzNDRixPQUFPO3dCQUFFTjtvQkFBRztvQkFDWlMsTUFBTTt3QkFDSlIsS0FBS0EsT0FBT0csU0FBU0gsR0FBRzt3QkFDeEJDLE9BQU9BLFNBQVNFLFNBQVNGLEtBQUs7d0JBQzlCUCxVQUFVQSxZQUFZUyxTQUFTVCxRQUFRO3dCQUN2Q1EsV0FBV0EsYUFBYUMsU0FBU0QsU0FBUztvQkFDNUM7Z0JBQ0Y7Z0JBQ0EsT0FBT2YscURBQVlBLENBQUNRLElBQUksQ0FBQztvQkFBRWMsU0FBUztvQkFBTWxCLFVBQVVlO2dCQUFRO1lBQzlEO1FBQ0Y7UUFFQSxzQkFBc0I7UUFDdEIsTUFBTUksVUFBVSxNQUFNdEIsK0NBQU1BLENBQUNHLFFBQVEsQ0FBQ29CLE1BQU0sQ0FBQztZQUMzQ0gsTUFBTTtnQkFDSlIsS0FBS0EsT0FBTztnQkFDWkMsT0FBT0EsU0FBUztnQkFDaEJQLFVBQVVBLFlBQVk7Z0JBQ3RCUSxXQUFXQSxhQUFhO1lBQzFCO1FBQ0Y7UUFFQSxPQUFPZixxREFBWUEsQ0FBQ1EsSUFBSSxDQUFDO1lBQUVjLFNBQVM7WUFBTWxCLFVBQVVtQjtRQUFRLEdBQUc7WUFBRUUsUUFBUTtRQUFJO0lBQy9FLEVBQUUsT0FBT0MsS0FBSztRQUNaLE9BQU8xQixxREFBWUEsQ0FBQ1EsSUFBSSxDQUFDO1lBQUVtQixPQUFPO1FBQWtCLEdBQUc7WUFBRUYsUUFBUTtRQUFJO0lBQ3ZFO0FBQ0YiLCJzb3VyY2VzIjpbIndlYnBhY2s6Ly9icmFuY29uZXQtazhzLW1hbmFnZXIvLi9zcmMvYXBwL2FwaS92YXJzL3JvdXRlLnRzP2MyMmMiXSwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgTmV4dFJlcXVlc3QsIE5leHRSZXNwb25zZSB9IGZyb20gXCJuZXh0L3NlcnZlclwiO1xuaW1wb3J0IHByaXNtYSBmcm9tIFwiQC9saWIvZGJcIjtcblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIEdFVCgpIHtcbiAgY29uc3QgdmFycyA9IGF3YWl0IHByaXNtYS52YXJpYWJsZS5maW5kTWFueSh7XG4gICAgb3JkZXJCeTogeyBjYXRlZ29yeTogXCJhc2NcIiB9LFxuICB9KTtcbiAgcmV0dXJuIE5leHRSZXNwb25zZS5qc29uKHZhcnMpO1xufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gUE9TVChyZXF1ZXN0OiBOZXh0UmVxdWVzdCkge1xuICB0cnkge1xuICAgIGNvbnN0IGJvZHkgPSBhd2FpdCByZXF1ZXN0Lmpzb24oKTtcbiAgICBjb25zdCB7IGlkLCBrZXksIHZhbHVlLCBjYXRlZ29yeSwgZW5jcnlwdGVkIH0gPSBib2R5O1xuXG4gICAgaWYgKGlkKSB7XG4gICAgICAvLyBVcGRhdGUgZXhpc3RpbmcgdmFyaWFibGVcbiAgICAgIGNvbnN0IGV4aXN0aW5nID0gYXdhaXQgcHJpc21hLnZhcmlhYmxlLmZpbmRVbmlxdWUoeyB3aGVyZTogeyBpZCB9IH0pO1xuICAgICAgaWYgKGV4aXN0aW5nKSB7XG4gICAgICAgIGNvbnN0IHVwZGF0ZWQgPSBhd2FpdCBwcmlzbWEudmFyaWFibGUudXBkYXRlKHtcbiAgICAgICAgICB3aGVyZTogeyBpZCB9LFxuICAgICAgICAgIGRhdGE6IHtcbiAgICAgICAgICAgIGtleToga2V5IHx8IGV4aXN0aW5nLmtleSxcbiAgICAgICAgICAgIHZhbHVlOiB2YWx1ZSA/PyBleGlzdGluZy52YWx1ZSxcbiAgICAgICAgICAgIGNhdGVnb3J5OiBjYXRlZ29yeSB8fCBleGlzdGluZy5jYXRlZ29yeSxcbiAgICAgICAgICAgIGVuY3J5cHRlZDogZW5jcnlwdGVkID8/IGV4aXN0aW5nLmVuY3J5cHRlZCxcbiAgICAgICAgICB9LFxuICAgICAgICB9KTtcbiAgICAgICAgcmV0dXJuIE5leHRSZXNwb25zZS5qc29uKHsgc3VjY2VzczogdHJ1ZSwgdmFyaWFibGU6IHVwZGF0ZWQgfSk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgLy8gQ3JlYXRlIG5ldyB2YXJpYWJsZVxuICAgIGNvbnN0IGNyZWF0ZWQgPSBhd2FpdCBwcmlzbWEudmFyaWFibGUuY3JlYXRlKHtcbiAgICAgIGRhdGE6IHtcbiAgICAgICAga2V5OiBrZXkgfHwgXCJuZXdfdmFyXCIsXG4gICAgICAgIHZhbHVlOiB2YWx1ZSB8fCBcIlwiLFxuICAgICAgICBjYXRlZ29yeTogY2F0ZWdvcnkgfHwgXCJnZW5lcmFsXCIsXG4gICAgICAgIGVuY3J5cHRlZDogZW5jcnlwdGVkIHx8IGZhbHNlLFxuICAgICAgfSxcbiAgICB9KTtcblxuICAgIHJldHVybiBOZXh0UmVzcG9uc2UuanNvbih7IHN1Y2Nlc3M6IHRydWUsIHZhcmlhYmxlOiBjcmVhdGVkIH0sIHsgc3RhdHVzOiAyMDEgfSk7XG4gIH0gY2F0Y2ggKGVycikge1xuICAgIHJldHVybiBOZXh0UmVzcG9uc2UuanNvbih7IGVycm9yOiBcIkludmFsaWQgcmVxdWVzdFwiIH0sIHsgc3RhdHVzOiA0MDAgfSk7XG4gIH1cbn0iXSwibmFtZXMiOlsiTmV4dFJlc3BvbnNlIiwicHJpc21hIiwiR0VUIiwidmFycyIsInZhcmlhYmxlIiwiZmluZE1hbnkiLCJvcmRlckJ5IiwiY2F0ZWdvcnkiLCJqc29uIiwiUE9TVCIsInJlcXVlc3QiLCJib2R5IiwiaWQiLCJrZXkiLCJ2YWx1ZSIsImVuY3J5cHRlZCIsImV4aXN0aW5nIiwiZmluZFVuaXF1ZSIsIndoZXJlIiwidXBkYXRlZCIsInVwZGF0ZSIsImRhdGEiLCJzdWNjZXNzIiwiY3JlYXRlZCIsImNyZWF0ZSIsInN0YXR1cyIsImVyciIsImVycm9yIl0sInNvdXJjZVJvb3QiOiIifQ==\n//# sourceURL=webpack-internal:///(rsc)/./src/app/api/vars/route.ts\n");

/***/ }),

/***/ "(rsc)/./src/lib/db.ts":
/*!***********************!*\
  !*** ./src/lib/db.ts ***!
  \***********************/
/***/ ((__unused_webpack_module, __webpack_exports__, __webpack_require__) => {

"use strict";
eval("__webpack_require__.r(__webpack_exports__);\n/* harmony export */ __webpack_require__.d(__webpack_exports__, {\n/* harmony export */   \"default\": () => (__WEBPACK_DEFAULT_EXPORT__),\n/* harmony export */   prisma: () => (/* binding */ prisma)\n/* harmony export */ });\n/* harmony import */ var _prisma_client__WEBPACK_IMPORTED_MODULE_0__ = __webpack_require__(/*! @prisma/client */ \"@prisma/client\");\n/* harmony import */ var _prisma_client__WEBPACK_IMPORTED_MODULE_0___default = /*#__PURE__*/__webpack_require__.n(_prisma_client__WEBPACK_IMPORTED_MODULE_0__);\n\nconst globalForPrisma = global;\nconst prisma = globalForPrisma.prisma ?? new _prisma_client__WEBPACK_IMPORTED_MODULE_0__.PrismaClient();\nif (true) globalForPrisma.prisma = prisma;\n/* harmony default export */ const __WEBPACK_DEFAULT_EXPORT__ = (prisma);\n//# sourceURL=[module]\n//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiKHJzYykvLi9zcmMvbGliL2RiLnRzIiwibWFwcGluZ3MiOiI7Ozs7Ozs7QUFBOEM7QUFFOUMsTUFBTUMsa0JBQWtCQztBQUlqQixNQUFNQyxTQUFTRixnQkFBZ0JFLE1BQU0sSUFBSSxJQUFJSCx3REFBWUEsR0FBRztBQUVuRSxJQUFJSSxJQUFxQyxFQUFFSCxnQkFBZ0JFLE1BQU0sR0FBR0E7QUFFcEUsaUVBQWVBLE1BQU1BLEVBQUMiLCJzb3VyY2VzIjpbIndlYnBhY2s6Ly9icmFuY29uZXQtazhzLW1hbmFnZXIvLi9zcmMvbGliL2RiLnRzPzllNGYiXSwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgUHJpc21hQ2xpZW50IH0gZnJvbSBcIkBwcmlzbWEvY2xpZW50XCI7XG5cbmNvbnN0IGdsb2JhbEZvclByaXNtYSA9IGdsb2JhbCBhcyB1bmtub3duIGFzIHtcbiAgcHJpc21hOiBQcmlzbWFDbGllbnQgfCB1bmRlZmluZWQ7XG59O1xuXG5leHBvcnQgY29uc3QgcHJpc21hID0gZ2xvYmFsRm9yUHJpc21hLnByaXNtYSA/PyBuZXcgUHJpc21hQ2xpZW50KCk7XG5cbmlmIChwcm9jZXNzLmVudi5OT0RFX0VOViAhPT0gXCJwcm9kdWN0aW9uXCIpIGdsb2JhbEZvclByaXNtYS5wcmlzbWEgPSBwcmlzbWE7XG5cbmV4cG9ydCBkZWZhdWx0IHByaXNtYTsiXSwibmFtZXMiOlsiUHJpc21hQ2xpZW50IiwiZ2xvYmFsRm9yUHJpc21hIiwiZ2xvYmFsIiwicHJpc21hIiwicHJvY2VzcyJdLCJzb3VyY2VSb290IjoiIn0=\n//# sourceURL=webpack-internal:///(rsc)/./src/lib/db.ts\n");

/***/ })

};
;

// load runtime
var __webpack_require__ = require("../../../webpack-runtime.js");
__webpack_require__.C(exports);
var __webpack_exec__ = (moduleId) => (__webpack_require__(__webpack_require__.s = moduleId))
var __webpack_exports__ = __webpack_require__.X(0, ["vendor-chunks/next"], () => (__webpack_exec__("(rsc)/./node_modules/next/dist/build/webpack/loaders/next-app-loader/index.js?name=app%2Fapi%2Fvars%2Froute&page=%2Fapi%2Fvars%2Froute&appPaths=&pagePath=private-next-app-dir%2Fapi%2Fvars%2Froute.ts&appDir=%2Fhome%2Fbrajam%2Frepos%2Fbranconet-homelab%2Fk8s-rewrite%2Ffront-end%2Fsrc%2Fapp&pageExtensions=tsx&pageExtensions=ts&pageExtensions=jsx&pageExtensions=js&rootDir=%2Fhome%2Fbrajam%2Frepos%2Fbranconet-homelab%2Fk8s-rewrite%2Ffront-end&isDev=true&tsconfigPath=tsconfig.json&basePath=&assetPrefix=&nextConfigOutput=&preferredRegion=&middlewareConfig=e30%3D!")));
module.exports = __webpack_exports__;

})();