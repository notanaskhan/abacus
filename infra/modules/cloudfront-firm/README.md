# cloudfront-firm

The firm app edge (Q-01-T15): SPA through OAC, `/v1/*` to the internal ALB via a VPC origin,
security headers, `/healthz` and `/readyz` refused at the edge. Default CloudFront host until the
firm domain exists (DEC-1003).

The origin request policy (`Managed-AllViewerExceptHostHeader`) sends the ALB's own name as
`Host`, so `firm-edge.js` passes the viewer's host on `/v1/*` (both behaviors) as
`X-Forwarded-Host`, replacing any value the viewer sent. The API believes it only from the load
balancer (`proxy_trusted_hosts`), judges it against `trusted_hosts` and reads it as the viewer
host: a branding hint and a session pin, never a tenant (TASK-6990, DEC-3990; ADR-163 §5).
