import prisma from "./db";
import { JOB_CHUNK_CHARS, type JobSlice } from "./job-stream";

export function jobIdValid(value: string | null): value is string {
  return typeof value === "string" && /^[A-Za-z0-9_-]{1,128}$/.test(value);
}
export async function readJobSlice(id: string, cursor: number, client: Pick<typeof prisma, "$queryRaw"> = prisma): Promise<JobSlice | null> {
  // SQLite substr/length count Unicode code points, avoiding UTF-16 cursor drift.
  const rows = await client.$queryRaw<Array<{ output: string; total: bigint; status: string }>>`
    SELECT substr(output, ${cursor + 1}, ${JOB_CHUNK_CHARS}) AS output,
           length(output) AS total, status FROM jobs WHERE id = ${id} LIMIT 1`;
  const row = rows[0];
  if (!row) return null;
  return { output: row.output, nextOffset: cursor + Array.from(row.output).length, total: Number(row.total), status: row.status };
}
export async function readJobTail(id: string, chars: number, client: Pick<typeof prisma, "$queryRaw"> = prisma) {
  const rows = await client.$queryRaw<Array<{ output: string; total: bigint }>>`
    SELECT substr(output, -${chars}) AS output, length(output) AS total FROM jobs WHERE id = ${id} LIMIT 1`;
  const row = rows[0];
  if (!row) return null;
  const total = Number(row.total);
  return { output: row.output, total, cursor: total, truncated: total > chars };
}
