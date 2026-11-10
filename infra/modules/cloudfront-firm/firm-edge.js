// The firm app's viewer-request function (Q-01-T15; ADR-152; TASK-6990, DEC-3990):
// - /healthz and /readyz answer 403 at the edge, in any case and with a trailing slash: only the
//   internal load balancer probes them.
// - /v1/* goes to the API with the viewer's Host as X-Forwarded-Host: the origin request policy
//   (Managed-AllViewerExceptHostHeader) sends the ALB's own name as Host, and the API believes
//   X-Forwarded-Host from the load balancer. A viewer-supplied X-Forwarded-Host is always dropped.
// Every other request passes unchanged.
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
  }
  return request;
}
