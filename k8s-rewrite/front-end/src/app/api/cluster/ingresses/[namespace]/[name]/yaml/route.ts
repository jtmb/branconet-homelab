import { resourceYamlGet, resourceYamlPut } from "@/lib/resource-yaml";

export const GET = resourceYamlGet("ingress");
export const PUT = resourceYamlPut("ingress");
