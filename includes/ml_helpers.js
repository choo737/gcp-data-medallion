// Gate optional MLOps XAI ledger models when ml_audit_project is unconfigured.

const PLACEHOLDER_PROJECTS = new Set([
  "",
  "example-ml-ops",
  "placeholder",
  "your-ml-audit-project-id",
  "your-ml-ops-project-id",
]);

function getVars() {
  if (
    typeof dataform !== "undefined" &&
    dataform.projectConfig &&
    dataform.projectConfig.vars
  ) {
    return dataform.projectConfig.vars;
  }
  return {};
}

function hasMlAuditLedger(varsOverride) {
  const vars = varsOverride !== undefined ? varsOverride : getVars();
  if (!vars || typeof vars !== "object") {
    return false;
  }
  const rawProj = vars.ml_audit_project;
  if (typeof rawProj !== "string") {
    return false;
  }
  const trimmed = rawProj.trim().toLowerCase();
  if (
    !trimmed ||
    PLACEHOLDER_PROJECTS.has(trimmed) ||
    trimmed.startsWith("example-") ||
    trimmed.startsWith("your-")
  ) {
    return false;
  }
  return true;
}

module.exports = {
  hasMlAuditLedger,
};
