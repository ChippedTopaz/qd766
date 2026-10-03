/** Remove completed OAuth response parameters, never application filter state. */
export function cleanLoginSearch(search) {
    const params = new URLSearchParams(search);
    const issuer = params.get("iss");
    const oauthResponse = (params.has("state") && (params.has("code") || params.has("error")))
        || issuer === "https://accounts.google.com" || issuer === "accounts.google.com";
    if (!oauthResponse)
        return null;
    for (const key of ["state", "code", "iss", "authuser", "prompt", "session_state",
        "error", "error_description", "error_uri", "id_token", "access_token", "token_type", "expires_in"]) {
        params.delete(key);
    }
    // `scope` is also the QD766 all/formality filter. Preserve those values.
    const appScopes = params.getAll("scope").filter(value => value === "all" || value === "formality");
    params.delete("scope");
    for (const value of appScopes)
        params.append("scope", value);
    const remaining = params.toString();
    return remaining ? `?${remaining}` : "";
}
//# sourceMappingURL=login-url.js.map