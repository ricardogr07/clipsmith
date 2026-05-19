import { type NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function proxy(req: NextRequest, path: string[]): Promise<NextResponse> {
  const url = new URL(`${API_BASE}/${path.join("/")}`);
  url.search = req.nextUrl.search;

  const headers = new Headers(req.headers);
  headers.delete("host");
  // Inject API key server-side so it is never exposed to the browser
  const apiKey = process.env.API_KEY;
  if (apiKey) {
    headers.set("X-Api-Key", apiKey);
  }

  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  try {
    const upstream = await fetch(url.toString(), {
      method: req.method,
      headers,
      body: hasBody ? await req.text() : undefined,
    });
    const text = await upstream.text();
    return new NextResponse(text, {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("Content-Type") ?? "application/json" },
    });
  } catch {
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
