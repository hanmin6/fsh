# Feature Specification: CRM Web Domain and Web-Only Delivery

**Feature Branch**: `codex/muse-crm-mcp`
**Created**: 2026-10-02
**Status**: Draft
**Input**: Make `gzfusanhesp.com` the employee CRM web entry point and stop advancing desktop/Android clients.

## Scope

This feature prepares the CRM web application for deployment behind the
`gzfusanhesp.com` HTTPS origin. EspoCRM, MariaDB, the scheduled daemon and
WebSocket service remain the CRM runtime. A Caddy edge service terminates TLS
and routes browser traffic to the internal application services.

Employee access uses EspoCRM's native username/password login and server-side
ACLs. The former public shared-workspace login is disabled by default and is
not used for the employee deployment.

The independent public website `fshfoodingredients.com` is outside this
feature and receives no DNS, hosting or application changes.

## Requirements

### CRM-WEB-01 Canonical origin

The production configuration defaults to `https://gzfusanhesp.com`, supports
an explicit WebSocket origin, and does not publish database or WebSocket
container ports directly to the public network.

### CRM-WEB-02 HTTPS edge

A reproducible Caddy configuration terminates HTTP/HTTPS, redirects HTTP to
HTTPS, routes normal requests to EspoCRM and upgrades WebSocket requests to the
WebSocket service. Certificates and Caddy state persist outside the source
tree.

### CRM-WEB-03 Employee login

The CRM login page presents the branded native login form. Public shared
workspace authentication is disabled by default; an explicit environment flag
is required to enable the legacy marker, and it is not enabled by the CRM
deployment template.

### CRM-WEB-04 Web-only product surface

The Web workspace is the maintained user surface. Android and desktop client
code remains available as an archived snapshot but is removed from the active
verification workflow and is not described as a current production client.

### CRM-WEB-05 Deployment safety

The deployment template keeps outbound communication paused by default,
keeps secrets in the server environment, exposes health checks, and documents
backup, rebuild, rollback and domain verification steps.

## Non-goals

- Changing the independent public website or its DNS.
- Deleting the Android repository or historical client snapshots.
- Adding public employee registration or changing CRM business permissions.
- Deploying real platform sending or changing the global outbound pause.
