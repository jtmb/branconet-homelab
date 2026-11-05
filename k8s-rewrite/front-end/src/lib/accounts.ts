import { NextResponse } from "next/server";
import prisma from "./db";
import { AccountError, AccountStore } from "./account-store";

export const accounts = new AccountStore(prisma);
export function accountFailure(error: unknown) {
  return error instanceof AccountError
    ? NextResponse.json({ error: error.message }, { status: error.status })
    : NextResponse.json({ error: "Account operation unavailable" }, { status: 503 });
}
