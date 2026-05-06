/** Shared user-facing API strings (imported by api.ts and apiClient.ts to avoid circular imports). */

export const apiConnectionMessage =
  "Backend unreachable. In Vercel set NEXT_PUBLIC_API_URL to your HTTPS Railway API URL (see docs/VERCEL_PRODUCTION_CHECKLIST.md).";

export const apiUnreachableMessage =
  "We couldn't reach your voice backend. Check NEXT_PUBLIC_API_URL and that the Railway API is running.";
