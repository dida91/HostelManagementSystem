/**
 * Backend-for-frontend proxy.
 *
 * The browser never calls FastAPI directly. This handler forwards the request
 * with its httpOnly session cookies and relays Set-Cookie back, so tokens stay
 * out of JavaScript entirely (an XSS bug cannot exfiltrate a session).
 */
import { NextRequest, NextResponse } from "next/server";

const API = process.env.API_INTERNAL_URL ?? "http://localhost:8000";
const HOP_BY_HOP = new Set(["connection", "keep-alive", "transfer-encoding", "upgrade", "host"]);

async function proxy(req: NextRequest, path: string[]): Promise<NextResponse> {
  const target = `${API}/api/v1/${path.join("/")}${req.nextUrl.search}`;

  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) headers.set(key, value);
  });

  // Raw bytes, never text: decoding a multipart body as UTF-8 corrupts binary
  // uploads such as PDFs.
  const body = ["GET", "HEAD"].includes(req.method) ? undefined : await req.arrayBuffer();

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: req.method,
      headers,
      body,
      redirect: "manual",
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      { title: "upstream_unavailable", detail: "The service is unavailable. Please try again." },
      { status: 503 },
    );
  }

  // A 204, 205 or 304 must have no body at all: even an empty buffer makes the
  // Response constructor throw, turning a successful DELETE into a 500.
  const empty = req.method === "HEAD" || [204, 205, 304].includes(upstream.status);
  const res = new NextResponse(empty ? null : await upstream.arrayBuffer(), { status: upstream.status });
  upstream.headers.forEach((value, key) => {
    const k = key.toLowerCase();
    if (HOP_BY_HOP.has(k) || k === "content-encoding" || k === "content-length") return;
    if (k === "set-cookie") res.headers.append("set-cookie", value);
    else res.headers.set(key, value);
  });
  return res;
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path);
}
export async function POST(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path);
}
export async function PATCH(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path);
}
export async function PUT(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path);
}
export async function DELETE(req: NextRequest, ctx: Ctx) {
  return proxy(req, (await ctx.params).path);
}
