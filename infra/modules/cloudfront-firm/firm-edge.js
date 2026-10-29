// The firm app's viewer-request function (Q-01-T15; ADR-152): /healthz and /readyz answer 403 at
// the edge, in any case and with a trailing slash: only the internal load balancer probes them.
// Every other request passes unchanged.
function handler(event) {
  var request = event.request;
  var uri = request.uri.toLowerCase();
  if (uri === "/healthz" || uri === "/readyz" || uri === "/healthz/" || uri === "/readyz/") {
    return { statusCode: 403, statusDescription: "Forbidden" };
  }
  return request;
}
