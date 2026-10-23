// CloudFront Function (cloudfront-js-2.0, viewer request) for the PR preview host (Q-01-T49, D-OPS-13).
//
// Every request is refused with 403 unless it carries the gate cookie, whose value must equal the
// `gate-key` entry of the associated KeyValueStore. The key never appears in git, in Terraform state
// or in a PR comment: the builder puts it into the store by hand (infra/README.md) and keeps the
// founder-only link `/__preview/login?k=<key>`, which sets the cookie.
//
//   /__preview/login?k=<key>  sets the gate cookie, then redirects to /
//   /__preview/pr/<n>         (gate cookie required) selects PR <n>, then redirects to /
//   anything else             (gate cookie and a selected PR required) served from pr-<n>/ in the
//                             bucket; a path without a file extension is the SPA's index.html
//
// The bundle is the same fixture build `make dev-fixtures` serves, at the root path, so nothing in
// the app needs a base path. One browser views one PR at a time; opening another PR's link switches.
import cf from "cloudfront";

// One store is associated with this function, so the handle needs no ID.
const kvs = cf.kvs();
const GATE_COOKIE = "abacus_preview";
const PR_COOKIE = "abacus_preview_pr";
const MAX_AGE_SECONDS = 1209600; // 14 days, the bucket's expiry
const PR_NUMBER = /^[0-9]{1,6}$/;
const PR_LINK = /^\/__preview\/pr\/([0-9]{1,6})\/?$/;
const MIN_KEY_LENGTH = 32;

function deny() {
  return {
    statusCode: 403,
    statusDescription: "Forbidden",
    headers: { "cache-control": { value: "no-store" } },
  };
}

function redirect(cookies) {
  return {
    statusCode: 302,
    statusDescription: "Found",
    headers: { location: { value: "/" }, "cache-control": { value: "no-store" } },
    cookies: cookies,
  };
}

function cookie(value) {
  return {
    value: value,
    attributes: "Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=" + MAX_AGE_SECONDS,
  };
}

function cookieValue(request, name) {
  const found = request.cookies[name];
  return found ? found.value : "";
}

async function handler(event) {
  const request = event.request;
  const uri = request.uri;

  let key = "";
  try {
    key = await kvs.get("gate-key");
  } catch (err) {
    return deny(); // no key in the store yet: nothing is served
  }
  if (!key || key.length < MIN_KEY_LENGTH) {
    return deny();
  }

  if (uri === "/__preview/login") {
    const given = request.querystring.k ? request.querystring.k.value : "";
    if (given !== key) {
      return deny();
    }
    const cookies = {};
    cookies[GATE_COOKIE] = cookie(key);
    return redirect(cookies);
  }

  if (cookieValue(request, GATE_COOKIE) !== key) {
    return deny();
  }

  const link = uri.match(PR_LINK);
  if (link) {
    const cookies = {};
    cookies[PR_COOKIE] = cookie(link[1]);
    return redirect(cookies);
  }

  const pr = cookieValue(request, PR_COOKIE);
  if (!PR_NUMBER.test(pr) || uri.indexOf("/__preview/") === 0) {
    return deny();
  }

  const last = uri.split("/").pop();
  request.uri = "/pr-" + pr + (last.indexOf(".") === -1 ? "/index.html" : uri);
  return request;
}
