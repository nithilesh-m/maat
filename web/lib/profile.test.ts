import { describe, expect, it } from "vitest";
import { validateProfileYaml } from "./profile";

const BASE = `profile_version: 1\nname: x\nsystem_type: rag\ndescription: d\nintended_use: u\ndeclared_risk_tier: limited\n`;

describe("profile yaml", () => {
  it("accepts minimal valid", () => {
    expect(validateProfileYaml(`${BASE}target: {adapter: chat, model_family: mistral}\n`).ok).toBe(true);
  });
  it("reports missing keys", () => {
    const r = validateProfileYaml("name: x\n");
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error).toContain("profile_version");
  });
  it("reports yaml errors", () => {
    expect(validateProfileYaml("name: [\n").ok).toBe(false);
  });
  it("rejects non-mappings", () => {
    const r = validateProfileYaml("- a\n- b\n");
    expect(r.ok).toBe(false);
  });
  it("warns on literal secrets", () => {
    const r = validateProfileYaml(`${BASE}target: {adapter: chat, model_family: m, auth_env: sk-abc123}\n`);
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.error).toContain("environment variable NAME");
      expect(r.error).not.toContain("sk-abc123"); // never echo the pasted secret
    }
  });
});
