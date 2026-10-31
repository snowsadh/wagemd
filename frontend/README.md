# frontend/ — WAGE.md web app

Next.js 14 (App Router) + Tailwind + Server Components. Minimal by design — Tailwind
defaults, no animations (see SPEC.md "Risk: what NOT to spend time on").

## Pages

| Route | File | Purpose |
|---|---|---|
| `/` | `app/page.tsx` | Hero + prominent search bar |
| `/company/[slug]` | `app/company/[slug]/page.tsx` | Percentile table + local company brief link |
| `/negotiate` | `app/negotiate/page.tsx` | Offer form → calls the Counselor agent |
| `/about` | `app/about/page.tsx` | Methodology (cut candidate) |
| `/briefs` | `app/briefs/page.tsx` | Index of company briefs stored in Tiger Data |
| `/briefs/[slug]` | `app/briefs/[slug]/page.tsx` | Generated company brief |

Server components request data from the FastAPI middleware via
[lib/api.ts](lib/api.ts). Set `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).

## Run

```bash
npm install
npm run dev      # http://localhost:3000  (or: make frontend from repo root)
```
