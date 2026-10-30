import { createJudgeDemoProxy } from "../../../lib/judge-demo-proxy.mjs";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const proxy = createJudgeDemoProxy();

export const GET = proxy;
export const POST = proxy;
