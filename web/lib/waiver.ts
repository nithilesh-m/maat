export interface WaiverInput {
  id: string;
  clause_id: string;
  owner: string;
  scope: string;
  expiry: string;
  compensations: string[];
}

export function validateWaiver(w: WaiverInput, now: Date = new Date()): string[] {
  const errs: string[] = [];
  for (const k of ["id", "clause_id", "owner", "scope"] as const)
    if (!w[k]?.trim()) errs.push(`${k} is required`);
  const exp = new Date(w.expiry);
  if (Number.isNaN(exp.getTime())) errs.push("Expiry is not a valid date");
  else {
    if (exp <= now) errs.push("Expiry must be in the future");
    if (exp.getTime() - now.getTime() > 90 * 24 * 3600 * 1000)
      errs.push("Expiry must be within 90 days");
  }
  if (!w.compensations.filter((c) => c.trim()).length)
    errs.push("At least one compensating measure is required");
  return errs;
}
