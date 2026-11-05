// Keep the original core API for direct-reader parity controls; the evaluation facade is worker-owned.
export { DirectAccountReader, accountDatabaseLocation } from "./direct-account-core";
export type { SessionRow, AccountRow } from "./direct-account-core";
import { WorkerAccountReader } from "./worker-account-reader";
const scope = globalThis as typeof globalThis & { __bortusDirectAccountReader?: WorkerAccountReader };
export const directAccountReader = scope.__bortusDirectAccountReader ??= new WorkerAccountReader();
