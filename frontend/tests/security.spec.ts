import { expect, request as playwrightRequest, test, type APIRequestContext, type Page } from "@playwright/test";
import fs from "fs";
import path from "path";

const FRONTEND_URL = process.env.FRONTEND_URL || "https://new-tqq.vercel.app";
const BACKEND_URL = process.env.BACKEND_URL || "https://new-tqq-excd.vercel.app";
const ADMIN_USERNAME = process.env.ADMIN_USERNAME || "admin";
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || "admin123";
const MASTER_FILE = process.env.MASTER_FILE || "C:\\Users\\ASUS\\Downloads\\Data Master Trial (1).xlsx";
const REKAP_FILE = process.env.REKAP_FILE || "C:\\Users\\ASUS\\Downloads\\Rekapitulasi Trial (1).xlsx";
const PUBLIC_TEST_NIM = process.env.PUBLIC_TEST_NIM || "25081494046";
const RUN_MUTATION_E2E = process.env.RUN_MUTATION_E2E === "1";
const EXPECT_PUBLIC_NIM_FOUND = process.env.EXPECT_PUBLIC_NIM_FOUND === "1";
const INVALID_FILE = path.join(__dirname, "fixtures", "not-excel.txt");

const SECRET_MARKERS = [
  "APP_AUTH_TOKEN",
  "GROQ_API_KEY",
  "SUPABASE_SERVICE_ROLE_KEY",
  "ADMIN_PASSWORD",
  "service_role",
  "gsk_",
];

const SECRET_VALUES = (process.env.SECRET_VALUES_TO_SCAN || "")
  .split(",")
  .map((value) => value.trim())
  .filter((value) => value.length >= 8);

async function loginViaApi(api: APIRequestContext) {
  const response = await api.post(`${BACKEND_URL}/api/auth/login`, {
    data: { username: ADMIN_USERNAME, password: ADMIN_PASSWORD },
  });
  expect(response.status()).toBe(200);
  const body = await response.json();
  expect(body.token).toEqual(expect.any(String));
  return body.token as string;
}

async function loginViaUi(page: Page) {
  await page.goto(FRONTEND_URL);
  await page.getByRole("button", { name: /login admin/i }).click();
  await page.getByPlaceholder("Username").fill(ADMIN_USERNAME);
  await page.getByPlaceholder("Password").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: /^masuk$/i }).click();
  await expect(page.getByRole("heading", { name: /analisis data/i })).toBeVisible();
}

test.describe("security audit", () => {
  test("login admin valid", async ({ page }) => {
    await loginViaUi(page);
  });

  test("login admin invalid", async ({ page }) => {
    await page.goto(FRONTEND_URL);
    await page.getByRole("button", { name: /login admin/i }).click();
    await page.getByPlaceholder("Username").fill(ADMIN_USERNAME);
    await page.getByPlaceholder("Password").fill("definitely-wrong-audit-password");
    await page.getByRole("button", { name: /^masuk$/i }).click();
    await expect(page.getByText(/username atau password salah|login gagal/i)).toBeVisible();
  });

  test("admin endpoints reject missing and invalid token", async ({ request }) => {
    const approvalPayload = { session_id: "00000000-0000-0000-0000-000000000000", approvals: [] };

    await expect((await request.post(`${BACKEND_URL}/api/apply-approvals`, { data: approvalPayload })).status()).toBe(401);
    await expect((await request.post(`${BACKEND_URL}/api/generate-excel`, { data: approvalPayload })).status()).toBe(401);
    await expect((await request.get(`${BACKEND_URL}/api/download/00000000-0000-0000-0000-000000000000`)).status()).toBe(401);

    const invalidToken = { Authorization: "Bearer invalid-audit-token" };
    await expect((await request.post(`${BACKEND_URL}/api/apply-approvals`, { headers: invalidToken, data: approvalPayload })).status()).toBe(401);
    await expect((await request.post(`${BACKEND_URL}/api/generate-excel`, { headers: invalidToken, data: approvalPayload })).status()).toBe(401);
  });

  test("analyze endpoint rejects missing token before processing upload", async ({ request }) => {
    const response = await request.post(`${BACKEND_URL}/api/analyze`, {
      multipart: {
        mode: "with_master",
        use_groq: "false",
        rekap_file: {
          name: "not-excel.txt",
          mimeType: "text/plain",
          buffer: Buffer.from("not xlsx"),
        },
      },
    });
    expect(response.status()).toBe(401);
  });

  test("CORS rejects untrusted origin and allows configured frontend origin", async ({ request }) => {
    const untrusted = await request.fetch(`${BACKEND_URL}/api/generate-excel`, {
      method: "OPTIONS",
      headers: {
        Origin: "https://evil.example",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
      },
    });
    expect(untrusted.headers()["access-control-allow-origin"]).toBeFalsy();

    const trusted = await request.fetch(`${BACKEND_URL}/api/generate-excel`, {
      method: "OPTIONS",
      headers: {
        Origin: FRONTEND_URL,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
      },
    });
    expect(trusted.status()).toBeLessThan(300);
    expect(trusted.headers()["access-control-allow-origin"]).toBe(FRONTEND_URL);
  });

  test("upload file invalid ditolak", async ({ page }) => {
    await loginViaUi(page);
    await page.getByLabel("Upload Data Master").setInputFiles(INVALID_FILE);
    await page.getByLabel("Upload Rekapitulasi Nilai").setInputFiles(INVALID_FILE);
    await page.getByRole("button", { name: /analisis data/i }).click();
    await expect(page.getByText(/harus berformat \.xlsx|bukan workbook|tidak bisa dibaca/i)).toBeVisible();
  });

  test("public search NIM tidak mengembalikan data berlebihan", async ({ request }) => {
    const shortQuery = await request.get(`${BACKEND_URL}/api/public/search-nim?nim=2`);
    expect(shortQuery.status()).toBe(200);
    const shortBody = await shortQuery.json();
    expect(shortBody.rows || []).toHaveLength(0);

    const exact = await request.get(`${BACKEND_URL}/api/public/search-nim?nim=${encodeURIComponent(PUBLIC_TEST_NIM)}`);
    expect(exact.status()).toBe(200);
    const exactBody = await exact.json();
    expect((exactBody.rows || []).length).toBeLessThanOrEqual(1);
    if (EXPECT_PUBLIC_NIM_FOUND) {
      expect(exactBody.rows?.[0]?.NIM).toBe(PUBLIC_TEST_NIM);
    }
  });

  test("frontend bundle dan response network tidak membocorkan secret", async ({ page }) => {
    const findings: string[] = [];
    const scan = (source: string, url: string) => {
      for (const marker of [...SECRET_MARKERS, ...SECRET_VALUES]) {
        if (source.includes(marker)) findings.push(`${marker} in ${url}`);
      }
    };

    page.on("response", async (response) => {
      const contentType = response.headers()["content-type"] || "";
      if (!/(javascript|json|text|html)/i.test(contentType)) return;
      try {
        const body = await response.text();
        scan(body, response.url());
      } catch {
        // Some streamed/opaque responses are not readable from Playwright.
      }
    });

    await page.goto(FRONTEND_URL);
    await page.waitForLoadState("networkidle");
    scan(await page.content(), "rendered-dom");
    expect(findings).toEqual([]);
  });
});

test.describe("mutation E2E", () => {
  test.skip(!RUN_MUTATION_E2E, "Set RUN_MUTATION_E2E=1 only on staging/test Supabase table; generate replaces public lookup data.");

  test("upload file valid, generate Excel final, download, dan public search", async ({ page }) => {
    expect(fs.existsSync(MASTER_FILE), `Missing MASTER_FILE: ${MASTER_FILE}`).toBeTruthy();
    expect(fs.existsSync(REKAP_FILE), `Missing REKAP_FILE: ${REKAP_FILE}`).toBeTruthy();

    await loginViaUi(page);
    await page.getByRole("button", { name: /pakai data master/i }).click();
    await page.getByLabel("Upload Data Master").setInputFiles(MASTER_FILE);
    await page.getByLabel("Upload Rekapitulasi Nilai").setInputFiles(REKAP_FILE);
    await page.getByRole("button", { name: /analisis data/i }).click();
    await expect(page.getByRole("heading", { name: /dashboard analisis/i })).toBeVisible({ timeout: 60_000 });

    await page.getByRole("button", { name: /lihat validasi nama/i }).click();
    await page.getByRole("button", { name: /setujui semua/i }).click();
    await page.getByRole("button", { name: /terapkan pilihan/i }).click();
    await expect(page.getByRole("heading", { name: /preview output/i })).toBeVisible({ timeout: 60_000 });

    await page.getByRole("button", { name: /^download$/i }).click();
    await page.getByRole("button", { name: /generate excel final/i }).click();
    await expect(page.getByRole("button", { name: /download excel final/i })).toBeVisible({ timeout: 60_000 });

    const api = await playwrightRequest.newContext();
    const search = await api.get(`${BACKEND_URL}/api/public/search-nim?nim=${encodeURIComponent(PUBLIC_TEST_NIM)}`);
    expect(search.status()).toBe(200);
    const body = await search.json();
    expect(body.rows?.[0]?.NIM).toBe(PUBLIC_TEST_NIM);
    await api.dispose();
  });

  test("generate Excel final dan download via API", async ({ request }) => {
    expect(fs.existsSync(MASTER_FILE), `Missing MASTER_FILE: ${MASTER_FILE}`).toBeTruthy();
    expect(fs.existsSync(REKAP_FILE), `Missing REKAP_FILE: ${REKAP_FILE}`).toBeTruthy();

    const token = await loginViaApi(request);
    const analyze = await request.post(`${BACKEND_URL}/api/analyze`, {
      headers: { Authorization: `Bearer ${token}` },
      multipart: {
        mode: "with_master",
        use_groq: "false",
        master_file: {
          name: path.basename(MASTER_FILE),
          mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          buffer: fs.readFileSync(MASTER_FILE),
        },
        rekap_file: {
          name: path.basename(REKAP_FILE),
          mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          buffer: fs.readFileSync(REKAP_FILE),
        },
      },
    });
    expect(analyze.status()).toBe(200);
    const analysis = await analyze.json();
    expect(analysis.session_id).toEqual(expect.any(String));
    const approvals = (analysis.recommendations || []).map((item: Record<string, string>) => ({
      mapping_id: item.mapping_id,
      approved: true,
      matched_name: item.nama_master,
      matched_class: item.kode_kelas_pai,
    }));

    const generated = await request.post(`${BACKEND_URL}/api/generate-excel`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { session_id: analysis.session_id, approvals },
    });
    expect(generated.status()).toBe(200);
    const generatedBody = await generated.json();
    expect(generatedBody.download_url).toEqual(expect.stringMatching(/^\/api\/download\//));

    const download = await request.get(`${BACKEND_URL}${generatedBody.download_url}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(download.status()).toBe(200);
    expect(download.headers()["content-type"]).toContain("spreadsheetml.sheet");
  });
});
