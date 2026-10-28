import { Storage } from "@google-cloud/storage";
import { NextRequest, NextResponse } from "next/server";


const BUCKET = "velib-pulse-data-velib-pulse";

function getStorage() {
  const credentialsJson = process.env.GCP_SERVICE_ACCOUNT_JSON;

  return new Storage({
    projectId: "velib-pulse",
    credentials: credentialsJson
      ? JSON.parse(credentialsJson)
      : undefined,
  });
}

// Cache only the manifest, never the release JSON files.
// This cache is per serverless instance and expires after 30 seconds.
const MANIFEST_TTL_MS = 30_000;

let manifestCache: {
  body: string;
  expiresAt: number;
} | null = null;

let manifestRequest: Promise<string> | null = null;

async function getManifest(): Promise<string> {
  const now = Date.now();

  if (manifestCache && now < manifestCache.expiresAt) {
    return manifestCache.body;
  }

  // Share one GCS request between concurrent requests on this instance.
  if (!manifestRequest) {
    manifestRequest = getStorage()
      .bucket(BUCKET)
      .file("dashboard/manifest.json")
      .download()
      .then(([contents]) => {
        const body = contents.toString("utf-8");

        // Validate before caching.
        JSON.parse(body);

        manifestCache = {
          body,
          expiresAt: Date.now() + MANIFEST_TTL_MS,
        };

        return body;
      })
      .finally(() => {
        manifestRequest = null;
      });
  }

  return manifestRequest;
}

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
    const body =
      objectPath === "dashboard/manifest.json"
        ? await getManifest()
        : (
            await getStorage()
              .bucket(BUCKET)
              .file(objectPath)
              .download()
          )[0].toString("utf-8");

    return new NextResponse(body, {
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
