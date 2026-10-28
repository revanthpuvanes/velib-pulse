import { Storage } from "@google-cloud/storage";
import { NextRequest, NextResponse } from "next/server";


const BUCKET = "velib-pulse-data-velib-pulse";

const storage = new Storage({
  projectId: "velib-pulse",
  credentials: process.env.GCP_SERVICE_ACCOUNT_JSON
    ? JSON.parse(process.env.GCP_SERVICE_ACCOUNT_JSON)
    : undefined,
});

const ALLOWED_FILES = new Set([
  "stations.json",
  "hourly.json",
  "health.json",
  "insights.json",
]);

export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;

  let objectPath: string;

  if (path.length === 1 && path[0] === "manifest.json") {
    objectPath = "dashboard/manifest.json";
  } else if (
    path.length === 3 &&
    path[0] === "releases" &&
    /^[A-Za-z0-9_-]+$/.test(path[1]) &&
    ALLOWED_FILES.has(path[2])
  ) {
    objectPath = `dashboard/releases/${path[1]}/${path[2]}`;
  } else {
    return NextResponse.json(
      { error: "Invalid dashboard data path" },
      { status: 400 },
    );
  }

  try {
    const [contents] = await storage.bucket(BUCKET).file(objectPath).download();

    return new NextResponse(contents.toString("utf-8"), {
      status: 200,
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    console.error("GCS dashboard read failed:", objectPath, error);

    return NextResponse.json(
      { error: "Dashboard data temporarily unavailable" },
      { status: 503 },
    );
  }
}
