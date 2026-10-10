import type { Prisma, PrismaClient } from "@prisma/client";

export class AccountError extends Error {
  constructor(public readonly status: number, message: string) { super(message); }
}

export type AccountActor = { id: string; sessionVersion: number };
const publicUser = { id: true, username: true, role: true, createdAt: true } as const;

export class AccountStore {
  constructor(private readonly db: PrismaClient) {}

  async registrationOpen(client: Prisma.TransactionClient = this.db) {
    if (await client.user.count() === 0 || process.env.ALLOW_REGISTRATION === "true") return true;
    return (await client.appSetting.findUnique({ where: { key: "allow_registration" } }))?.value === "true";
  }

  private async serialized<T>(operation: (tx: Prisma.TransactionClient) => Promise<T>): Promise<T> {
    for (let attempt = 0; attempt < 4; attempt++) {
      try {
        return await this.db.$transaction(async (tx) => {
          // SQLite serializes writers. Acquire that lock before any count/actor reads,
          // so a competing process cannot commit between the check and the change.
          await tx.accountLock.update({ where: { id: 1 }, data: { locked: 0 } });
          return operation(tx);
        }, { maxWait: 10000, timeout: 10000 });
      } catch (error) {
        if (error instanceof AccountError) throw error;
        const code = (error as { code?: string }).code;
        if (code === "P2002") throw new AccountError(409, "Username already taken");
        if (!["P2034", "P2028", "P1008"].includes(code || "")) throw error;
        if (attempt === 3) throw new AccountError(503, "Account change is busy; retry shortly");
        await new Promise(resolve => setTimeout(resolve, 25 * (attempt + 1)));
      }
    }
    throw new AccountError(503, "Account change is busy; retry shortly");
  }

  private async writer(tx: Prisma.TransactionClient, actor: AccountActor) {
    const user = await tx.user.findUnique({ where: { id: actor.id } });
    if (!user || user.sessionVersion !== actor.sessionVersion) throw new AccountError(401, "Authentication required");
    if (user.role !== "write") throw new AccountError(403, "Write access required");
  }

  register(input: { username: string; passwordHash: string }) {
    return this.serialized(async tx => {
      if (!await this.registrationOpen(tx)) throw new AccountError(403, "Registration is locked");
      const role = await tx.user.count() === 0 ? "write" : "readonly";
      return tx.user.create({ data: { ...input, role }, select: { ...publicUser, sessionVersion: true } });
    });
  }

  create(actor: AccountActor, input: { username: string; passwordHash: string; role: "write" | "readonly" }) {
    return this.serialized(async tx => {
      await this.writer(tx, actor);
      return tx.user.create({ data: input, select: publicUser });
    });
  }

  update(actor: AccountActor, id: string, input: { role?: "write" | "readonly"; passwordHash?: string }) {
    return this.serialized(async tx => {
      await this.writer(tx, actor);
      if (actor.id === id && input.role !== undefined) throw new AccountError(403, "You cannot change your own role");
      const target = await tx.user.findUnique({ where: { id } });
      if (!target) throw new AccountError(404, "User not found");
      if (target.role === "write" && input.role === "readonly" && await tx.user.count({ where: { role: "write" } }) <= 1)
        throw new AccountError(403, "Cannot demote the last write user");
      return tx.user.update({
        where: { id },
        data: { ...input, ...(input.passwordHash !== undefined ? { sessionVersion: { increment: 1 } } : {}) },
        select: publicUser,
      });
    });
  }

  delete(actor: AccountActor, id: string) {
    return this.serialized(async tx => {
      await this.writer(tx, actor);
      if (actor.id === id) throw new AccountError(403, "You cannot delete yourself");
      const target = await tx.user.findUnique({ where: { id } });
      if (!target) throw new AccountError(404, "User not found");
      if (target.role === "write" && await tx.user.count({ where: { role: "write" } }) <= 1)
        throw new AccountError(403, "Cannot delete the last write user");
      await tx.user.delete({ where: { id } });
    });
  }
}
