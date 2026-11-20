/**
 * Qualification-only interruption barrier. Uses unchanged real transport and
 * controller decision path; holds after acknowledged PATCH, before completion.
 * Never configured in the production/scheduled template.
 */
import fs from "node:fs/promises"
import { runOnce, transport } from "./controller.mjs"

async function main() {
  const c = JSON.parse(await fs.readFile("/controller/enrollment.json", "utf8"))
  const token = (await fs.readFile("/var/run/rotation/token", "utf8")).trim()
  const apiCA = await fs.readFile("/var/run/rotation/ca.crt")
  const servingCA = await fs.readFile("/serving/ca.crt")
  const io = transport(c, token, apiCA, servingCA)
  const patch = io.patch
  io.patch = async (...args) => {
    await patch(...args)
    console.log(JSON.stringify({ qualificationBarrier: "acknowledged-patch-before-completion" }))
    await new Promise(() => { setInterval(() => {}, 1000) })
  }
  const result = await runOnce(c, io)
  console.log(JSON.stringify(result))
}
main().catch(() => {
  console.log(JSON.stringify({ state: "attention", reason: "qualification_interruption_path_failed" }))
  process.exitCode = 1
})
