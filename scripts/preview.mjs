// Fictional, local-only UI preview. No Supabase requests or personal data.
import http from "node:http";
import { readFile } from "node:fs/promises";
const id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
const demo = [
  {
    id,
    owner_id: "fictional-preview",
    saved: true,
    vacancy: {
      employer: "Fictional Harbour Hotel",
      title: "Food & Beverage Attendant",
      source: "Demonstration only",
      location: "Auckland CBD",
      distance: 1,
      job_type: "Part-time",
      match: 85,
      why: "Fictional preview of customer service and teamwork matching.",
      found: "2026-10-14",
      last_verified: "2026-10-14",
      recommended: true,
      is_new: true,
      vacancy_state: "open",
      url: "https://example.org/fictional",
    },
  },
  {
    id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    dismissed: true,
    vacancy: {
      employer: "Fictional Cafe",
      title: "Cafe Assistant",
      location: "Ponsonby",
      match: 70,
      source: "Demonstration only",
      found: "2026-10-14",
      last_verified: "2026-10-14",
      vacancy_state: "verification_unknown",
    },
  },
];
http
  .createServer(async (req, res) => {
    try {
      const path = new URL(req.url, "http://localhost").pathname;
      res.setHeader("Cache-Control", "no-store");
      if (path.startsWith("/api/")) {
        res.setHeader("Content-Type", "application/json");
        if (path.endsWith("/decision")) {
          let body = "";
          for await (const part of req) body += part;
          const action = JSON.parse(body).action;
          const job = demo.find((j) => j.id === path.split("/")[3]);
          const map = {
            save: ["saved", true],
            unsave: ["saved", false],
            dismiss: ["dismissed", true],
            restore: ["dismissed", false],
            applied: ["applied", true],
          };
          if (job && map[action]) job[map[action][0]] = map[action][1];
          res.end('{"ok":true}');
          return;
        }
        res.end(
          JSON.stringify(
            path === "/api/health"
              ? {
                  sync: [
                    {
                      last_successful_sync: "Fictional preview — not connected",
                    },
                  ],
                  sources: [],
                }
              : demo,
          ),
        );
        return;
      }
      const files = {
        "/": "index.html",
        "/app.js": "app.js",
        "/style.css": "style.css",
      };
      if (!files[path]) {
        res.writeHead(404);
        res.end();
        return;
      }
      res.setHeader(
        "Content-Type",
        path.endsWith(".js")
          ? "text/javascript"
          : path.endsWith(".css")
            ? "text/css"
            : "text/html",
      );
      let body = await readFile(
        new URL("../web/public/" + files[path], import.meta.url),
        "utf8",
      );
      if (path === "/")
        body = body.replace(
          "<body>",
          '<body><p style="padding:12px">Fictional local preview — no real vacancies or backend connection.</p>',
        );
      res.end(body);
    } catch {
      res.writeHead(500);
      res.end("Preview error");
    }
  })
  .listen(8790, "127.0.0.1", () =>
    console.log("Fictional preview: http://127.0.0.1:8790"),
  );
