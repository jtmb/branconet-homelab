import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

const require = createRequire(resolve("package.json"));
const { Address4, Address6, AddressError } = require("ip-address");
const { SocksClient } = require("socks");

test("IPv6 zones and CIDR retain their parsed meaning", () => {
  for (const [input, form, zone, subnet] of [
    ["::1", "::1", "", 128],
    ["2001:0db8:0:0:0:0:0:1/64", "2001:db8::1", "", 64],
    ["fe80::1%eth0", "fe80::1", "%eth0", 128],
    ["fe80::1%a%b", "fe80::1", "%a%b", 128],
    ["fe80::1%", "fe80::1", "%", 128],
    ["fe80::1/64%eth0", "fe80::1", "%eth0", 64],
    [`fe80::1%${"x".repeat(256)}`, "fe80::1", `%${"x".repeat(256)}`, 128],
  ]) {
    const parsed = new Address6(input);
    assert.equal(parsed.correctForm(), form);
    assert.equal(parsed.zone, zone);
    assert.equal(parsed.subnetMask, subnet);
    assert.equal(Address6.isValid(input), true);
  }
});

test("zone rejection avoids the quadratic unanchored matcher", () => {
  const originalExec = RegExp.prototype.exec;
  let unsafeCalls = 0;
  RegExp.prototype.exec = function (input) {
    if (this.source === "%.*$" && this.flags === "") unsafeCalls++;
    return Reflect.apply(originalExec, this, [input]);
  };
  try {
    for (const terminator of ["\n", "\r", "\u2028", "\u2029"]) {
      for (const input of [
        `${"%".repeat(4096)}${terminator}`,
        `fe80::1%${"%".repeat(4096)}${terminator}tail`,
      ]) {
        assert.equal(Address6.isValid(input), false);
        assert.throws(() => new Address6(input), AddressError);
      }
    }
  } finally {
    RegExp.prototype.exec = originalExec;
  }
  assert.equal(unsafeCalls, 0, "Address6 invoked the vulnerable quadratic zone matcher");
});

test("invalid IPv6 inputs still fail as AddressError", () => {
  for (const input of ["f".repeat(46), "::/129", "::/0/1", "fe80::1%a\nb%c", "1:2:3:4:5:6:7:8:9"]) {
    assert.equal(Address6.isValid(input), false);
    assert.throws(() => new Address6(input), AddressError);
  }
});

test("IPv4 parsing remains compatible", () => {
  const parsed = new Address4("192.0.2.17/24");
  assert.equal(parsed.correctForm(), "192.0.2.17");
  assert.equal(parsed.subnetMask, 24);
  assert.equal(Address4.isValid("256.0.0.1"), false);
});

test("SOCKS IPv6 decoding retains exact sixteen-byte address and payload", () => {
  const host = "2001:db8:0000:0000:0000:0000:0000:1234";
  const data = Buffer.from([0, 255, 37, 10]);
  const frame = SocksClient.createUDPFrame({ remoteHost: { host, port: 443 }, data });
  assert.equal(frame[3], 4);
  assert.equal(frame.length, 4 + 16 + 2 + data.length);
  const parsed = SocksClient.parseUDPFrame(frame);
  assert.equal(parsed.frameNumber, 0);
  assert.deepEqual(parsed.remoteHost, { host: new Address6(host).canonicalForm(), port: 443 });
  assert.deepEqual(parsed.data, data);
  assert.equal(Address6.fromByteArray([...frame.subarray(4, 20)]).canonicalForm(), new Address6(host).canonicalForm());
});

test("the installed Kubernetes client imports with the patched dependency", async () => {
  const sdk = await import(pathToFileURL(require.resolve("@kubernetes/client-node")).href);
  assert.equal(typeof sdk.KubeConfig, "function");
  assert.equal(typeof sdk.dumpYaml, "function");
});
