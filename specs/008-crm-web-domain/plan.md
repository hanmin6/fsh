# Implementation Plan: CRM Web Domain and Web-Only Delivery

1. Add canonical CRM origin, bind-address and public-workspace safety
   environment variables to `.env.example` and `compose.yaml`.
2. Add a production Caddy edge profile with persistent certificate/config
   volumes, HTTP-to-HTTPS redirect, CRM routing and WebSocket upgrade routing.
3. Make the branded CRM login use native employee credentials and gate the
   legacy public workspace marker behind an opt-in server flag.
4. Mark Android and desktop client surfaces as archived and remove Android from
   the active CI gate without deleting historical source.
5. Add offline contracts and a CRM deployment runbook covering DNS, HTTPS,
   health checks, backup, rebuild and rollback.

The EspoCRM and MariaDB data model stays unchanged. The reverse proxy owns the
public boundary; CRM ACL and native authentication remain the contract owner
for user access. Rollback is a configuration revert plus the previous Git
revision; no destructive database operation is required.
