(function () {
  "use strict";

  const storageKey = "astra.workspace.apiKey";
  const nativeFetch = window.fetch.bind(window);
  let apiKey = window.sessionStorage.getItem(storageKey) || "";
  let prompted = false;

  function setApiKey(value) {
    apiKey = String(value || "").trim();
    if (apiKey) window.sessionStorage.setItem(storageKey, apiKey);
    else window.sessionStorage.removeItem(storageKey);
  }

  window.ASTRA_API_AUTH = {
    setApiKey,
    clearApiKey: () => setApiKey(""),
  };

  window.fetch = function authenticatedFetch(input, init) {
    const url = new URL(typeof input === "string" ? input : input.url, window.location.href);
    const protectedApi = (
      url.origin === window.location.origin &&
      (url.pathname === "/api" || url.pathname.startsWith("/api/")) &&
      url.pathname !== "/api/health"
    );
    if (!protectedApi) return nativeFetch(input, init);

    if (!apiKey && !prompted) {
      prompted = true;
      setApiKey(window.prompt("ASTRA API key") || "");
    }
    const options = Object.assign({}, init || {});
    const headers = new Headers(options.headers || (typeof input !== "string" ? input.headers : undefined));
    if (apiKey && !headers.has("Authorization") && !headers.has("X-API-Key")) {
      headers.set("Authorization", `Bearer ${apiKey}`);
    }
    options.headers = headers;
    return nativeFetch(input, options);
  };
})();
