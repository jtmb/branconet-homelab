import { resourceYamlGet, resourceYamlPut } from "@/lib/resource-yaml";

export const GET = resourceYamlGet("deployment");
export const PUT = resourceYamlPut("deployment");
