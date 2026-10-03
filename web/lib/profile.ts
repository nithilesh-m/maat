import { load as loadYaml } from "js-yaml";

const REQUIRED = [
  "profile_version",
  "name",
  "system_type",
  "description",
  "intended_use",
  "declared_risk_tier",
  "target",
];

/** Fast client-side feedback only; the server's 422 message stays authoritative. */
export function validateProfileYaml(text: string): { ok: true } | { ok: false; error: string } {
  let doc: unknown;
  try {
    doc = loadYaml(text);
  } catch (e) {
    return { ok: false, error: `YAML error: ${(e as Error).message}` };
  }
  if (!doc || typeof doc !== "object" || Array.isArray(doc))
    return { ok: false, error: "Profile must be a YAML mapping" };
  const d = doc as Record<string, unknown>;
  const missing = REQUIRED.filter((k) => !(k in d));
  if (missing.length) return { ok: false, error: `Missing keys: ${missing.join(", ")}` };
  const auth = (d.target as Record<string, unknown> | undefined)?.auth_env;
  if (typeof auth === "string" && !/^[A-Z_][A-Z0-9_]*$/.test(auth))
    return {
      ok: false,
      error: "target.auth_env must be an environment variable NAME, not the secret itself",
    };
  return { ok: true };
}
