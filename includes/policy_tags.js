// Column governance helper for dual-tier BigQuery PII policy tags.

const POLICY_TAG_RESOURCE_REGEX =
  /^projects\/[a-z0-9-]+\/locations\/[a-z0-9-]+\/taxonomies\/[0-9]+\/policyTags\/[0-9]+$/;

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

function resolveVars(varsOverride) {
  if (varsOverride === undefined) {
    return getVars();
  }
  if (
    varsOverride === null ||
    typeof varsOverride !== "object" ||
    Array.isArray(varsOverride)
  ) {
    throw new Error("vars must be a plain object.");
  }
  return varsOverride;
}

function allowUntaggedPii(varsOverride) {
  const vars = resolveVars(varsOverride);
  if (vars.allow_untagged_pii === false) {
    return false;
  }
  if (
    typeof vars.allow_untagged_pii === "string" &&
    vars.allow_untagged_pii.trim().toLowerCase() === "false"
  ) {
    return false;
  }
  return true;
}

function validatePolicyTag(rawValue, varName) {
  if (rawValue === undefined || rawValue === null) {
    return "";
  }
  if (typeof rawValue !== "string") {
    throw new Error(`${varName} must be a string resource name.`);
  }
  const trimmed = rawValue.trim();
  if (trimmed.length === 0) {
    return "";
  }
  if (!POLICY_TAG_RESOURCE_REGEX.test(trimmed)) {
    throw new Error(
      `Invalid ${varName} "${trimmed}". Expected projects/{project}/locations/{location}/taxonomies/{id}/policyTags/{id}.`
    );
  }
  return trimmed;
}

function resolveTierPolicyTag(primaryKey, varsOverride) {
  const vars = resolveVars(varsOverride);
  const primary = validatePolicyTag(vars[primaryKey], primaryKey);
  const fallback = validatePolicyTag(vars.pii_policy_tag, "pii_policy_tag");
  const resolved = primary || fallback;

  if (resolved.length > 0) {
    return [resolved];
  }
  if (!allowUntaggedPii(vars)) {
    throw new Error(
      `${primaryKey} or pii_policy_tag is required when allow_untagged_pii is false.`
    );
  }
  return [];
}

function piiRestrictedPolicyTag(varsOverride) {
  return resolveTierPolicyTag("pii_restricted_policy_tag", varsOverride);
}

function piiMaskedPolicyTag(varsOverride) {
  return resolveTierPolicyTag("pii_masked_policy_tag", varsOverride);
}

function piiPolicyTag(varsOverride) {
  return piiMaskedPolicyTag(varsOverride);
}

function getPiiPolicyTag(varsOverride) {
  const vars = resolveVars(varsOverride);
  return validatePolicyTag(vars.pii_policy_tag, "pii_policy_tag");
}

function piiColumnConfig(description, tier = "masked", varsOverride) {
  const tags =
    tier === "restricted"
      ? piiRestrictedPolicyTag(varsOverride)
      : piiMaskedPolicyTag(varsOverride);
  if (tags.length > 0) {
    return {
      description: description,
      bigqueryPolicyTags: tags
    };
  }
  return {
    description: description
  };
}

module.exports = {
  getPiiPolicyTag,
  allowUntaggedPii,
  piiRestrictedPolicyTag,
  piiMaskedPolicyTag,
  piiPolicyTag,
  piiColumnConfig
};
