export function runtimeCapabilities(env: NodeJS.ProcessEnv = process.env, platform: NodeJS.Platform = process.platform) {
  return {
    provisioning: env.BORTUS_DISABLE_PROVISIONING !== "true" && !env.KUBERNETES_SERVICE_HOST,
    operatorShell: platform !== "win32" && env.BORTUS_DISABLE_OPERATOR_SHELL !== "true",
    podExec: env.BORTUS_DISABLE_POD_EXEC !== "true",
  };
}
