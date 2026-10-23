// Viewer-request function for the client portal (Q-01-T56; ADR-163 sections 3 and 4).
// - /healthz and /readyz answer 403 at the edge: only the load balancer probes them (ADR-152).
// - /v1/* goes to the API on the same origin. The viewer's Host is passed as X-Forwarded-Host, a
//   branding hint only (INV-4); a viewer-supplied X-Forwarded-Host is always replaced.
// - Hashed assets, runtime-config.json, portal.html and other root files pass through.
// - Every other path is a portal route at the origin root (/sign-in, /accept, /documents, ...)
//   and is served the portal entry, portal.html.
function handler(event) {
  var request = event.request;
  var uri = request.uri.toLowerCase();

  if (uri === "/healthz" || uri === "/readyz" || uri === "/healthz/" || uri === "/readyz/") {
    return { statusCode: 403, statusDescription: "Forbidden" };
  }

  if (uri.indexOf("/v1/") === 0) {
    var host = request.headers.host;
    delete request.headers["x-forwarded-host"];
    if (host && host.value) {
      request.headers["x-forwarded-host"] = { value: host.value };
    }
    return request;
  }

  if (uri.indexOf("/assets/") === 0 || uri === "/runtime-config.json" || uri === "/portal.html") {
    return request;
  }

  var last = uri.substring(uri.lastIndexOf("/") + 1);
  if (last.indexOf(".") !== -1) {
    return request;
  }

  request.uri = "/portal.html";
  return request;
}
