# AI Voice SaaS Architecture Pack

This folder contains the enterprise-grade blueprint for the AI voice calling SaaS platform.

Deliverables:

- [Final Architecture](final-architecture.md)
- [Folder Structure](folder-structure.md)
- [Backend Module Map](backend-module-map.md)
- [DB Schema](db-schema.md)
- [Deployment Guide](deployment-guide.md)
- [Scaling Guide](scaling-guide.md)
- [Observability Plan](observability-plan.md)
- [Security Checklist](security-checklist.md)
- [SaaS Roadmap](saas-roadmap.md)

Design target:

- Frontend: Next.js, Tailwind, shadcn/ui
- Backend: FastAPI services
- Voice: LiveKit realtime rooms
- Telephony: SIP trunks with Vobiz/Telnyx support
- Database: Supabase/Postgres
- Queue: Redis with Celery or BullMQ
- Deploy: Railway backend/workers, Vercel frontend, Docker
- Billing: Razorpay primary, Stripe optional
