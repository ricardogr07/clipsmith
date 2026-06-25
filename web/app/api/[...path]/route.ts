import { type NextRequest, NextResponse } from "next/server";

// API_BASE overrides NEXT_PUBLIC_API_BASE for server-side proxy calls in Docker Compose
// (web container reaches api container at http://api:8000, not localhost:8000)
const API_BASE =
  process.env.API_BASE ?? process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function proxy(req: NextRequest, path: string[]): Promise<NextResponse> {
  const url = new URL(`${API_BASE}/${path.join("/")}`);
  url.search = req.nextUrl.search;

  const headers: Record<string, string> = {};
  req.headers.forEach((value, key) => {
    if (key.toLowerCase() !== "host") headers[key] = value;
  });
  const apiKey = process.env.API_KEY;
  if (apiKey) {
    headers["x-api-key"] = apiKey;
  }

  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  try {
    const upstream = await fetch(url.toString(), {
      method: req.method,
      headers,
      body: hasBody ? await req.text() : undefined,
      cache: "no-store",
    });
    const buffer = await upstream.arrayBuffer();
    return new NextResponse(buffer, {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json" },
    });
  } catch (err) {
    console.error("[proxy] Backend unavailable:", url.toString(), (err as Error).message);
    return NextResponse.json({ detail: "Backend unavailable" }, { status: 503 });
  }
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
