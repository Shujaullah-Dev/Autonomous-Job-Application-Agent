# Job Agent frontend

From this directory, run `npm ci` and `npm run dev`. Open the Vite URL and choose **Explore the demo** for a complete sample journey without a backend.

Setup, architecture, API inventory, roadmap coverage, privacy limits, tests, and deployment instructions are in [the frontend handover](../docs/frontend.md). The full local QA plan for desktop and mobile is in [the testing guide](../docs/testing.md).

Private live features remain blocked pending verified server ownership checks. The frontend never uses a backend development credential. Supabase Auth is optional; browser-safe configuration is listed in `.env.example`. `VITE_API_BASE_URL` defaults to `http://127.0.0.1:8000`, and the backend allows the Vite development origins through CORS.
